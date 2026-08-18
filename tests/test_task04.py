import hashlib
import json
import shutil
from pathlib import Path

from harness.runner import load_task
from harness.tools import WorkspaceTools


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "task04_report_resources"
TASK_DIR = REPO_ROOT / "tasks" / TASK_ID
TEST_COMMAND = [
    "python",
    "-m",
    "pytest",
    "-q",
    "test_report_renderer.py",
]

PRIOR_TASK_HASHES = {
    "task01_exact/task.json": (
        "75dbf2309b5c022c6cf640f040cbbf1b81cad0928494671c1ce102fbdab613d4"
    ),
    "task01_exact/workspace/calculator.py": (
        "4dae1192612b8cb9b3d6573543722e14e9732bbdf98d2e25f8e5dc5abcbc0aa8"
    ),
    "task01_exact/workspace/test_calculator.py": (
        "f7faaa7431ba7b80eb0f6e42ca07fcd1204de09bc2af3a22e655c961c86ba169"
    ),
    "task02_config_path/task.json": (
        "45d90ae98d9f9c1710a93bd53abadead4a5a8744d6705506eeb58f0f85cd98a0"
    ),
    "task02_config_path/workspace/app.py": (
        "8d1a4acbc4008411461a541d37facc9ca9aee74d3fb2d2f5b6a779e8e385d68f"
    ),
    "task02_config_path/workspace/config/settings.json": (
        "70172183b7a477d0d5ab4072d593715c16a22ffde30c6099e180c7886ef9318f"
    ),
    "task02_config_path/workspace/test_app.py": (
        "20c9a89d72af36545cf793d37de012430828c29a5f48d0fa3eea761a4f6d1a5c"
    ),
    "task03_resource_path/task.json": (
        "3cd3c4a7d8a572b1f897056af3e609af49bd491e7e7e1d0739b2fde6658f6148"
    ),
    "task03_resource_path/workspace/assets/template.json": (
        "0531fdd05fd07b13e293735687aa729051d563e54a436ea4a65510f065bccb30"
    ),
    "task03_resource_path/workspace/template_loader.py": (
        "e7e13247c6ba135219b0ce9512e96c91dd26039167816af6b1f079dfcf3b673a"
    ),
    "task03_resource_path/workspace/test_template_loader.py": (
        "23af044bfa8bbd132d2d514e7e9c426734d06fcb065df6bd61661bd549a97717"
    ),
}


def copied_tools(tmp_path: Path) -> WorkspaceTools:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK_DIR / "workspace", workspace)
    return WorkspaceTools(workspace, TEST_COMMAND)


def test_task04_loads_through_existing_task_infrastructure():
    task = load_task(REPO_ROOT, TASK_ID)

    assert task["task_id"] == TASK_ID
    assert task["environment"] == {"language": "python"}
    assert task["test_command"] == TEST_COMMAND


def test_task04_pristine_evaluator_is_deterministic_with_mixed_results(
    tmp_path: Path,
):
    tools = copied_tools(tmp_path)

    first = tools.run_tests()
    second = tools.run_tests()

    assert first.returncode == second.returncode == 1
    assert "2 failed, 3 passed" in first.stdout
    assert "2 failed, 3 passed" in second.stdout


def test_task04_failure_is_specific_to_cwd_dependent_defaults(tmp_path: Path):
    tools = copied_tools(tmp_path)

    workspace_cases = tools.run_command(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            (
                "test_report_renderer.py::"
                "test_bundled_defaults_load_from_workspace_directory"
            ),
            "test_report_renderer.py::test_existing_default_report_output_is_preserved",
            (
                "test_report_renderer.py::"
                "test_explicit_resource_directory_remains_supported"
            ),
        ]
    )
    relocated_cases = tools.run_command(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            (
                "test_report_renderer.py::"
                "test_default_rendering_after_working_directory_changes"
            ),
            (
                "test_report_renderer.py::"
                "test_default_rendering_from_second_unrelated_directory"
            ),
        ]
    )

    assert workspace_cases.returncode == 0
    assert "3 passed" in workspace_cases.stdout
    assert relocated_cases.returncode == 1
    assert "2 failed" in relocated_cases.stdout
    assert "FileNotFoundError" in relocated_cases.stdout


def test_task04_explicit_override_already_works_and_is_public_contract(
    tmp_path: Path,
):
    tools = copied_tools(tmp_path)

    result = tools.run_command(
        [
            "python",
            "-m",
            "pytest",
            "-q",
            (
                "test_report_renderer.py::"
                "test_explicit_resource_directory_remains_supported"
            ),
        ]
    )

    assert result.returncode == 0
    assert "1 passed" in result.stdout


def test_task04_public_metadata_does_not_leak_solution():
    text = (TASK_DIR / "task.json").read_text(encoding="utf-8")
    metadata = json.loads(text)

    assert metadata["description"] == (
        "Report rendering succeeds when launched from the project workspace but "
        "fails in other execution contexts. Fix bundled rendering-resource "
        "loading while preserving support for caller-supplied resource "
        "directories and existing report output."
    )
    for forbidden in (
        "__file__",
        "Path(",
        "report_renderer/resources",
        "defaults.json",
        "expected patch",
        "module-relative",
    ):
        assert forbidden not in text


def test_tasks_01_through_03_are_unchanged():
    for relative_path, expected_hash in PRIOR_TASK_HASHES.items():
        content = (REPO_ROOT / "tasks" / relative_path).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_hash
