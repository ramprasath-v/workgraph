from pathlib import Path

import pytest

from harness.tools import ToolError, WorkspaceTools, reset_workspace


@pytest.fixture
def tools(tmp_path: Path) -> WorkspaceTools:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "valid.py").write_text("value = 1\n", encoding="utf-8")
    return WorkspaceTools(workspace, ["python", "-m", "pytest", "-q"])


def test_path_traversal_is_rejected(tools: WorkspaceTools):
    with pytest.raises(ToolError, match="escapes"):
        tools.read_file("../../forbidden.py")


def test_read_valid_file(tools: WorkspaceTools):
    assert tools.read_file("valid.py") == "value = 1\n"


def test_edit_valid_file(tools: WorkspaceTools):
    tools.write_file("valid.py", "value = 2\n")
    assert tools.read_file("valid.py") == "value = 2\n"


def test_forbidden_absolute_file_access(tools: WorkspaceTools):
    with pytest.raises(ToolError, match="absolute"):
        tools.read_file("/etc/passwd")


def test_non_allowlisted_command_is_rejected(tools: WorkspaceTools):
    with pytest.raises(ToolError, match="allowlisted"):
        tools.run_command(["sh", "-c", "touch escaped"])


def test_unsafe_test_runner_option_is_rejected(tools: WorkspaceTools):
    with pytest.raises(ToolError, match="unsafe command argument"):
        tools.run_command(["python", "-m", "pytest", "--basetemp=/tmp/escape"])


def test_reset_workspace_restores_pristine_files(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "active"
    source.mkdir()
    (source / "file.py").write_text("original\n", encoding="utf-8")
    reset_workspace(source, target)
    (target / "file.py").write_text("changed\n", encoding="utf-8")
    (target / "extra.py").write_text("extra\n", encoding="utf-8")

    reset_workspace(source, target)

    assert (target / "file.py").read_text(encoding="utf-8") == "original\n"
    assert not (target / "extra.py").exists()
