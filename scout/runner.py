"""Read-only scouting loop and structured handoff generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from harness.action_normalization import normalize_action
from harness.models import AgentContext, ModelAdapter, ModelOutputError
from harness.tools import ToolError, WorkspaceTools, reset_workspace

from .schema import ScoutHandoff


SCOUT_ACTIONS = ("list_files", "read_file", "run_tests")
HANDOFF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "items": {"type": "string", "maxLength": 400},
            "minItems": 1,
            "maxItems": 6,
        },
        "suspected_area": {"type": "string", "maxLength": 400},
        "recommended_investigation": {
            "type": "array",
            "items": {"type": "string", "maxLength": 400},
            "minItems": 1,
            "maxItems": 5,
        },
        "constraints": {
            "type": "array",
            "items": {"type": "string", "maxLength": 400},
            "minItems": 1,
            "maxItems": 5,
        },
    },
    "required": [
        "observations",
        "suspected_area",
        "recommended_investigation",
        "constraints",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class GeneratedHandoff:
    analysis: dict[str, Any]
    input_tokens: int
    output_tokens: int
    total_tokens: int


class HandoffGenerator(Protocol):
    def generate_handoff(self, prompt: str) -> GeneratedHandoff: ...


class VertexHandoffGenerator:
    """Structured handoff generation using an existing Vertex adapter client."""

    def __init__(self, model: ModelAdapter):
        if model.provider != "vertex" or not hasattr(model, "_client"):
            raise ValueError("live scout handoff generation requires Vertex")
        self.model = model

    def generate_handoff(self, prompt: str) -> GeneratedHandoff:
        try:
            response = self.model._client.models.generate_content(
                model=self.model.name,
                contents=prompt,
                config={
                    "system_instruction": (
                        "Produce a concise current-task scouting handoff. Do not "
                        "include code blocks, corrected source files, patches, or diffs."
                    ),
                    "response_mime_type": "application/json",
                    "response_json_schema": HANDOFF_SCHEMA,
                    "temperature": 0,
                },
            )
        except Exception as exc:
            provider_error = getattr(self.model, "_provider_error", None)
            if callable(provider_error):
                raise provider_error(exc) from exc
            raise RuntimeError("Vertex scout handoff request failed") from exc
        parsed = getattr(response, "parsed", None)
        if not isinstance(parsed, dict):
            text = getattr(response, "text", None)
            try:
                parsed = json.loads(text) if isinstance(text, str) else None
            except json.JSONDecodeError as exc:
                raise ModelOutputError("scout handoff was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ModelOutputError("scout handoff was not an object")
        usage = getattr(response, "usage_metadata", None)
        count = getattr(self.model, "_usage_count", None)
        if not callable(count):
            raise RuntimeError("Vertex adapter does not expose usage accounting")
        input_tokens = count(usage, "prompt_token_count")
        output_tokens = count(usage, "candidates_token_count")
        total_tokens = count(usage, "total_token_count") or (
            input_tokens + output_tokens
        )
        return GeneratedHandoff(parsed, input_tokens, output_tokens, total_tokens)


class ReadOnlyScoutTools:
    """Restricted view of one copied workspace with no mutation actions."""

    def __init__(self, tools: WorkspaceTools):
        self.tools = tools

    def execute_action(self, action: dict[str, Any]) -> Any:
        name = action.get("action") if isinstance(action, dict) else None
        if name not in SCOUT_ACTIONS:
            raise ToolError(f"action {name!r} is not allowed for a read-only scout")
        return self.tools.execute_action(action)


def _workspace_snapshot(workspace: Path) -> dict[str, bytes]:
    return {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    }


def _handoff_prompt(
    task_id: str,
    task_description: str,
    history: list[dict[str, Any]],
) -> str:
    return (
        "CURRENT-TASK SCOUTING TRANSCRIPT\n"
        f"Task ID: {task_id}\n"
        f"Public task: {task_description}\n\n"
        "The transcript below contains only actions and outputs from read-only "
        "inspection of the current task workspace. Produce a compact handoff for "
        "a downstream coding agent. Base every observation on this transcript. "
        "Do not include a complete corrected file, code block, patch, unified diff, "
        "or hidden evaluator information. Keep every field item on one line.\n\n"
        + json.dumps(history, indent=2, ensure_ascii=False)
    )


def _without_evaluator_internals(values: object) -> object:
    if not isinstance(values, list):
        return values
    markers = ("test_", "::test", "pytest", "assert ")
    return [
        value
        for value in values
        if not isinstance(value, str)
        or not any(marker in value.lower() for marker in markers)
    ]


def run_scout(
    repo_root: Path,
    task_id: str,
    task: dict[str, Any],
    model: ModelAdapter,
    handoff_generator: HandoffGenerator,
    *,
    max_steps: int = 8,
) -> tuple[ScoutHandoff, Path]:
    if max_steps < 1:
        raise ValueError("scout max_steps must be positive")
    repo_root = repo_root.resolve()
    workspace = reset_workspace(
        repo_root / "tasks" / task_id / "workspace",
        repo_root / ".workspaces" / f"{task_id}-scout",
    )
    pristine_snapshot = _workspace_snapshot(workspace)
    tools = ReadOnlyScoutTools(WorkspaceTools(workspace, task["test_command"]))
    history: list[dict[str, Any]] = []
    input_tokens = output_tokens = total_tokens = tool_calls = 0
    start = perf_counter()
    for step in range(1, max_steps + 1):
        context = AgentContext(
            task_id=task_id,
            task_description=(
                task["description"]
                + " You are a read-only scout. Inspect the current workspace and "
                "gather evidence for a downstream fixer. Do not modify any file."
            ),
            available_tools=SCOUT_ACTIONS,
            history=tuple(history),
            current_step=step,
            max_steps=max_steps,
        )
        try:
            response = model.generate_action(context)
        except ModelOutputError as exc:
            history.append({"action": None, "output": {"error": str(exc)}})
            continue
        input_tokens += response.input_tokens
        output_tokens += response.output_tokens
        total_tokens += response.total_tokens or (
            response.input_tokens + response.output_tokens
        )
        action = normalize_action(response.action)
        if action.get("action") == "finish":
            break
        try:
            output = tools.execute_action(action)
            tool_calls += 1
        except ToolError as exc:
            output = {"error": str(exc)}
        history.append({"action": action, "output": output})

    generated = handoff_generator.generate_handoff(
        _handoff_prompt(task_id, task["description"], history)
    )
    if _workspace_snapshot(workspace) != pristine_snapshot:
        raise RuntimeError("read-only scout changed current-task workspace files")
    input_tokens += generated.input_tokens
    output_tokens += generated.output_tokens
    total_tokens += generated.total_tokens
    elapsed = round(perf_counter() - start, 6)
    files_inspected = sorted(
        {
            entry["action"]["path"]
            for entry in history
            if isinstance(entry.get("action"), dict)
            and entry["action"].get("action") == "read_file"
            and isinstance(entry.get("output"), str)
        }
    )
    handoff = ScoutHandoff.create(
        task_id=task_id,
        producer_provider=model.provider,
        producer_model=model.name,
        observations=_without_evaluator_internals(
            generated.analysis.get("observations")
        ),
        suspected_area=generated.analysis.get("suspected_area"),
        recommended_investigation=_without_evaluator_internals(
            generated.analysis.get("recommended_investigation")
        ),
        constraints=_without_evaluator_internals(
            generated.analysis.get("constraints")
        ),
        files_inspected=files_inspected,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        elapsed_seconds=elapsed,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    path = handoff.write_json(repo_root / "scout_handoffs")
    return handoff, path
