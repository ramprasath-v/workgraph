from pathlib import Path

import pytest

from harness.action_normalization import normalize_action
from harness.agent import CodingAgent
from harness.models import AgentContext, ModelAdapter, ModelResponse
from harness.tools import ToolError, WorkspaceTools
from harness.trajectory import build_trajectory


@pytest.fixture
def tools(tmp_path: Path) -> WorkspaceTools:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("value = 1\n", encoding="utf-8")
    return WorkspaceTools(workspace, ["python", "-m", "pytest", "-q"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            {
                "action": "read_file",
                "path": "app.py",
                "content": "ignored",
                "command": ["pytest"],
            },
            {"action": "read_file", "path": "app.py"},
        ),
        (
            {
                "action": "write_file",
                "path": "app.py",
                "content": "value = 2\n",
                "command": ["pytest"],
                "extra": "ignored",
            },
            {
                "action": "write_file",
                "path": "app.py",
                "content": "value = 2\n",
            },
        ),
        (
            {
                "action": "run_tests",
                "path": "app.py",
                "content": "ignored",
                "command": ["pytest"],
            },
            {"action": "run_tests"},
        ),
        (
            {
                "action": "run_command",
                "command": ["python", "-m", "pytest", "-q"],
                "path": "app.py",
                "content": "ignored",
            },
            {
                "action": "run_command",
                "command": ["python", "-m", "pytest", "-q"],
            },
        ),
        (
            {
                "action": "finish",
                "path": "app.py",
                "content": "ignored",
                "command": ["pytest"],
            },
            {"action": "finish"},
        ),
    ],
)
def test_known_actions_keep_only_their_defined_fields(raw, expected):
    assert normalize_action(raw) == expected


def test_missing_required_field_remains_invalid(tools: WorkspaceTools):
    normalized = normalize_action(
        {"action": "read_file", "command": ["rm", "-rf", "/"]}
    )

    assert normalized == {"action": "read_file"}
    with pytest.raises(ToolError, match="invalid fields for read_file"):
        tools.execute_action(normalized)


def test_unsafe_path_remains_rejected(tools: WorkspaceTools):
    normalized = normalize_action(
        {"action": "read_file", "path": "../../outside.py", "content": ""}
    )

    with pytest.raises(ToolError, match="escapes"):
        tools.execute_action(normalized)


def test_unsafe_command_remains_rejected(tools: WorkspaceTools):
    normalized = normalize_action(
        {
            "action": "run_command",
            "command": ["rm", "-rf", "/"],
            "path": "app.py",
        }
    )

    with pytest.raises(ToolError, match="allowlisted"):
        tools.execute_action(normalized)


class ReadWithMaliciousExtrasAdapter(ModelAdapter):
    name = "malicious-extras"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        return ModelResponse(
            {
                "action": "read_file",
                "path": "app.py",
                "content": "source payload that must be discarded",
                "command": ["rm", "-rf", "/"],
            }
        )


class MissingReadPathAdapter(ModelAdapter):
    name = "missing-read-path"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        return ModelResponse(
            {"action": "read_file", "command": ["rm", "-rf", "/"]}
        )


def test_irrelevant_malicious_command_is_not_executed_and_history_is_normalized(
    tools: WorkspaceTools, monkeypatch: pytest.MonkeyPatch
):
    def unexpected_command(*args, **kwargs):
        raise AssertionError("discarded command was executed")

    monkeypatch.setattr("subprocess.run", unexpected_command)

    run = CodingAgent(
        ReadWithMaliciousExtrasAdapter(), tools, max_steps=1
    ).run("task", "description")

    assert run.history[0]["action"] == {
        "action": "read_file",
        "path": "app.py",
    }
    assert run.history[0]["output"] == "value = 1\n"
    trajectory = build_trajectory(run.history)
    assert trajectory == [
        {
            "step": 1,
            "action": "read_file",
            "target": "app.py",
            "outcome": "success",
        }
    ]
    assert "source payload" not in str(run.history[0]["action"])


def test_missing_required_field_has_concise_normalized_trajectory_error(
    tools: WorkspaceTools, monkeypatch: pytest.MonkeyPatch
):
    def unexpected_command(*args, **kwargs):
        raise AssertionError("discarded command was executed")

    monkeypatch.setattr("subprocess.run", unexpected_command)

    run = CodingAgent(MissingReadPathAdapter(), tools, max_steps=1).run(
        "task", "description"
    )

    assert run.history[0]["action"] == {"action": "read_file"}
    assert build_trajectory(run.history) == [
        {
            "step": 1,
            "action": "read_file",
            "target": None,
            "outcome": "error: invalid fields for read_file: ['action']",
        }
    ]
