import shutil
from pathlib import Path

from harness.runner import load_task
from harness.tools import WorkspaceTools, reset_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_task02_pristine_copy_fails_three_tests(tmp_path: Path):
    source = REPO_ROOT / "tasks" / "task02_config_path" / "workspace"
    workspace = tmp_path / "workspace"
    shutil.copytree(source, workspace)
    task = load_task(REPO_ROOT, "task02_config_path")

    result = WorkspaceTools(workspace, task["test_command"]).run_tests()

    assert result.returncode != 0
    assert "3 failed, 1 passed" in result.stdout


def test_task02_workspace_reset_restores_broken_source(tmp_path: Path):
    source = REPO_ROOT / "tasks" / "task02_config_path" / "workspace"
    active = tmp_path / "active"
    reset_workspace(source, active)
    (active / "app.py").write_text("# modified\n", encoding="utf-8")
    (active / "extra.txt").write_text("noise\n", encoding="utf-8")

    reset_workspace(source, active)

    assert (active / "app.py").read_text(encoding="utf-8") == (
        source / "app.py"
    ).read_text(encoding="utf-8")
    assert not (active / "extra.txt").exists()
