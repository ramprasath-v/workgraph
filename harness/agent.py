"""Generic coding-agent execution loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .action_normalization import normalize_action
from .models import AgentContext, ModelAdapter, ModelOutputError
from .tools import ToolError, WorkspaceTools


@dataclass(frozen=True)
class AgentRun:
    steps: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    history: tuple[dict[str, Any], ...]
    finished: bool
    max_steps_exhausted: bool


class CodingAgent:
    """One reusable loop, independent of provider and benchmark condition."""

    def __init__(self, model: ModelAdapter, tools: WorkspaceTools, max_steps: int = 20):
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.model = model
        self.tools = tools
        self.max_steps = max_steps

    def run(
        self,
        task_id: str,
        task_description: str,
        prior_experience: dict[str, Any] | None = None,
    ) -> AgentRun:
        history: list[dict[str, Any]] = []
        tool_calls = input_tokens = output_tokens = total_tokens = 0
        estimated_cost_usd = 0.0
        finished = False

        for step in range(1, self.max_steps + 1):
            context = AgentContext(
                task_id=task_id,
                task_description=task_description,
                available_tools=WorkspaceTools.ACTIONS,
                history=tuple(history),
                prior_experience=prior_experience,
                current_step=step,
                max_steps=self.max_steps,
            )
            try:
                response = self.model.generate_action(context)
            except ModelOutputError as exc:
                history.append(
                    {
                        "action": None,
                        "output": {"error": f"malformed model output: {exc}"},
                    }
                )
                continue
            input_tokens += response.input_tokens
            output_tokens += response.output_tokens
            total_tokens += (
                response.total_tokens
                if response.total_tokens is not None
                else response.input_tokens + response.output_tokens
            )
            if response.estimated_cost_usd is None:
                estimated_cost_usd = None
            elif estimated_cost_usd is not None:
                estimated_cost_usd += response.estimated_cost_usd
            action = normalize_action(response.action)
            name = action.get("action") if isinstance(action, dict) else None
            try:
                output = self.tools.execute_action(action)
            except ToolError as exc:
                output = {"error": str(exc)}
            history.append({"action": action, "output": output})
            if name == "finish" and output == {"finished": True}:
                finished = True
                break
            tool_calls += 1

        return AgentRun(
            steps=len(history),
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
            history=tuple(history),
            finished=finished,
            max_steps_exhausted=not finished and len(history) == self.max_steps,
        )
