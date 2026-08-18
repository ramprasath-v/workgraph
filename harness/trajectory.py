"""Deterministic, compact summaries of executed agent actions."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


_MAX_SUMMARY_CHARS = 160


def _concise(value: object) -> str:
    text = " ".join(str(value).split())
    if len(text) <= _MAX_SUMMARY_CHARS:
        return text
    return text[: _MAX_SUMMARY_CHARS - 3] + "..."


def _test_summary(output: dict[str, Any]) -> str:
    combined = f"{output.get('stdout', '')}\n{output.get('stderr', '')}"
    passed = sum(int(value) for value in re.findall(r"(\d+) passed", combined))
    failed = sum(int(value) for value in re.findall(r"(\d+) failed", combined))
    returncode = output.get("returncode")
    if returncode != 0 and failed == 0:
        failed = 1
    if passed or failed:
        return f"{passed} passed / {failed} failed"
    return f"exit {returncode}" if isinstance(returncode, int) else "completed"


def _target(action: dict[str, Any], name: str) -> str | None:
    if name in {"read_file", "write_file"}:
        path = action.get("path")
        return _concise(path) if isinstance(path, str) else None
    if name == "run_command":
        command = action.get("command")
        if isinstance(command, list):
            return _concise(" ".join(str(part) for part in command))
    return None


def _outcome(name: str, output: object) -> str:
    if isinstance(output, dict) and "error" in output:
        # Tool errors are useful, but cap them so malformed output cannot flood results.
        return f"error: {_concise(output['error'])}"
    if name in {"run_tests", "run_command"} and isinstance(output, dict):
        return _test_summary(output)
    if name == "list_files" and isinstance(output, list):
        return f"success ({len(output)} files)"
    return "success"


def build_trajectory(
    history: Iterable[dict[str, Any]],
) -> list[dict[str, object]]:
    """Project actual agent/tool history into a safe, concise trajectory."""

    trajectory: list[dict[str, object]] = []
    for step, entry in enumerate(history, start=1):
        action = entry.get("action")
        if not isinstance(action, dict):
            trajectory.append(
                {
                    "step": step,
                    "action": "model_output_error",
                    "target": None,
                    "outcome": "malformed model output",
                }
            )
            continue
        raw_name = action.get("action")
        name = raw_name if isinstance(raw_name, str) else "invalid_action"
        trajectory.append(
            {
                "step": step,
                "action": name,
                "target": _target(action, name),
                "outcome": _outcome(name, entry.get("output")),
            }
        )
    return trajectory


def trajectory_diagnostics(
    trajectory: Iterable[dict[str, object]],
) -> dict[str, object]:
    """Count basic action repetition without changing agent behavior."""

    entries = list(trajectory)
    action_names = [str(entry["action"]) for entry in entries]
    identities = [
        (str(entry["action"]), entry.get("target")) for entry in entries
    ]
    counts = Counter(identities)
    diagnostics: dict[str, object] = {
        "unique_actions": len(set(action_names)),
        "repeated_identical_actions": sum(
            count - 1 for count in counts.values() if count > 1
        ),
        "test_runs": action_names.count("run_tests"),
        "file_reads": action_names.count("read_file"),
        "file_writes": action_names.count("write_file"),
        "most_repeated_action": None,
    }
    if counts:
        (action, target), count = counts.most_common(1)[0]
        if count > 1:
            diagnostics["most_repeated_action"] = {
                "action": action,
                "target": target,
                "count": count,
            }
    return diagnostics
