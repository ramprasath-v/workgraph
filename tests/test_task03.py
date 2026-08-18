import json
import shutil
from pathlib import Path

from harness.tools import WorkspaceTools, reset_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "task03_resource_path"
TEST_COMMAND = [
    "python",
    "-m",
    "pytest",
    "-q",
    "test_template_loader.py",
]


def test_task03_pristine_workspace_fails(tmp_path: Path):
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK_DIR / "workspace", workspace)

    result = WorkspaceTools(workspace, TEST_COMMAND).run_tests()

    assert result.returncode != 0
    assert "3 failed, 1 passed" in result.stdout


def test_task03_reset_restores_broken_pristine_workspace(tmp_path: Path):
    active = reset_workspace(TASK_DIR / "workspace", tmp_path / "active")
    source = active / "template_loader.py"
    pristine = source.read_text(encoding="utf-8")
    source.write_text("changed\n", encoding="utf-8")

    reset_workspace(TASK_DIR / "workspace", active)

    assert source.read_text(encoding="utf-8") == pristine
    assert WorkspaceTools(active, TEST_COMMAND).run_tests().returncode != 0


def test_task03_public_metadata_contains_no_hidden_solution_or_task02_names():
    metadata_text = (TASK_DIR / "task.json").read_text(encoding="utf-8")
    metadata = json.loads(metadata_text)

    assert metadata["task_id"] == "task03_resource_path"
    for forbidden in (
        "app.py",
        "config/settings.json",
        "load_settings",
        "config_path",
        "__file__",
        "expected patch",
    ):
        assert forbidden not in metadata_text


def test_task03_fixture_does_not_copy_task02_vocabulary():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((TASK_DIR / "workspace").rglob("*"))
        if path.is_file() and path.suffix in {".py", ".json"}
    )
    for forbidden in (
        "app.py",
        "config/settings.json",
        "load_settings",
        "config_path",
    ):
        assert forbidden not in combined
