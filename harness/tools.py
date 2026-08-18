"""Validated, workspace-confined tools exposed to the coding agent."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolError(ValueError):
    """Raised when a requested tool action is invalid or unsafe."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def reset_workspace(source: Path, target: Path) -> Path:
    """Replace target with a clean copy of source."""

    source = source.resolve(strict=True)
    target = target.resolve(strict=False)
    if not source.is_dir():
        raise ToolError(f"workspace source is not a directory: {source}")
    if target == source or source in target.parents:
        raise ToolError("reset target must be separate from the source workspace")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target


class WorkspaceTools:
    """File and command tools constrained to one active task workspace."""

    ACTION_FIELDS = {
        "list_files": ("action",),
        "read_file": ("action", "path"),
        "write_file": ("action", "path", "content"),
        "run_command": ("action", "command"),
        "run_tests": ("action",),
        "finish": ("action",),
    }
    ACTIONS = tuple(ACTION_FIELDS)

    def __init__(self, workspace: Path, test_command: list[str], timeout: int = 30):
        self.workspace = workspace.resolve(strict=True)
        self.test_command = self._validate_command(test_command)
        self.timeout = timeout

    def resolve_path(self, relative_path: str, *, must_exist: bool = False) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ToolError("path must be a non-empty string")
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ToolError("absolute paths are forbidden")
        resolved = (self.workspace / candidate).resolve(strict=False)
        if resolved != self.workspace and self.workspace not in resolved.parents:
            raise ToolError("path escapes the active workspace")
        if must_exist and not resolved.is_file():
            raise ToolError(f"file does not exist: {relative_path}")
        return resolved

    def list_files(self) -> list[str]:
        return sorted(
            path.relative_to(self.workspace).as_posix()
            for path in self.workspace.rglob("*")
            if path.is_file() and self.workspace in path.resolve().parents
        )

    def read_file(self, path: str) -> str:
        return self.resolve_path(path, must_exist=True).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        destination = self.resolve_path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        return {"path": path, "bytes_written": len(content.encode("utf-8"))}

    def run_command(self, command: list[str]) -> CommandResult:
        command = self._validate_command(command)
        return self._execute(command)

    def run_tests(self) -> CommandResult:
        return self._execute(self.test_command)

    def execute_action(self, action: dict[str, Any]) -> Any:
        if not isinstance(action, dict):
            raise ToolError("action must be an object")
        name = action.get("action")
        if name not in self.ACTION_FIELDS:
            raise ToolError(f"unknown action: {name!r}")
        if set(action) != set(self.ACTION_FIELDS[name]):
            raise ToolError(f"invalid fields for {name}: {sorted(action)}")
        if name == "list_files":
            return self.list_files()
        if name == "read_file":
            return self.read_file(action["path"])
        if name == "write_file":
            return self.write_file(action["path"], action["content"])
        if name == "run_command":
            return self.run_command(action["command"]).to_dict()
        if name == "run_tests":
            return self.run_tests().to_dict()
        return {"finished": True}

    @staticmethod
    def _validate_command(command: list[str]) -> list[str]:
        if not isinstance(command, list) or not command or not all(
            isinstance(part, str) and part for part in command
        ):
            raise ToolError("command must be a non-empty list of strings")
        if command[0] == "pytest":
            arguments = command[1:]
        elif command[:3] in (
            ["python", "-m", "pytest"],
            ["python3", "-m", "pytest"],
            ["python", "-m", "unittest"],
            ["python3", "-m", "unittest"],
        ):
            arguments = command[3:]
        else:
            raise ToolError("command is not allowlisted")
        safe_flags = {"-q", "-v", "-vv", "-x", "--tb=short"}
        for argument in arguments:
            if argument in safe_flags or (
                argument.startswith("--maxfail=")
                and argument.removeprefix("--maxfail=").isdigit()
            ):
                continue
            path = Path(argument)
            if argument.startswith("-") or path.is_absolute() or ".." in path.parts:
                raise ToolError("unsafe command argument")
        return list(command)

    def _execute(self, command: list[str]) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolError(f"command execution failed: {exc}") from exc
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)
