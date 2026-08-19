import hashlib
import json
import shutil
from pathlib import Path

from experience.schema import ExperienceRecord, Verification
from harness.runner import load_task
from harness.tools import WorkspaceTools
from recipe.compiler import compile_recipe
from transfer.compiler import compile_transfer_knowledge


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "task05_identifier_normalization"
TASK_DIR = REPO_ROOT / "tasks" / TASK_ID
TEST_COMMAND = ["python", "-m", "pytest", "-q", "test_user_registry.py"]

PRIOR_TASK_HASHES = {
    "task01_exact/task.json": "75dbf2309b5c022c6cf640f040cbbf1b81cad0928494671c1ce102fbdab613d4",
    "task01_exact/workspace/calculator.py": "4dae1192612b8cb9b3d6573543722e14e9732bbdf98d2e25f8e5dc5abcbc0aa8",
    "task01_exact/workspace/test_calculator.py": "f7faaa7431ba7b80eb0f6e42ca07fcd1204de09bc2af3a22e655c961c86ba169",
    "task02_config_path/task.json": "45d90ae98d9f9c1710a93bd53abadead4a5a8744d6705506eeb58f0f85cd98a0",
    "task02_config_path/workspace/app.py": "8d1a4acbc4008411461a541d37facc9ca9aee74d3fb2d2f5b6a779e8e385d68f",
    "task02_config_path/workspace/config/settings.json": "70172183b7a477d0d5ab4072d593715c16a22ffde30c6099e180c7886ef9318f",
    "task02_config_path/workspace/test_app.py": "20c9a89d72af36545cf793d37de012430828c29a5f48d0fa3eea761a4f6d1a5c",
    "task03_resource_path/task.json": "3cd3c4a7d8a572b1f897056af3e609af49bd491e7e7e1d0739b2fde6658f6148",
    "task03_resource_path/workspace/assets/template.json": "0531fdd05fd07b13e293735687aa729051d563e54a436ea4a65510f065bccb30",
    "task03_resource_path/workspace/template_loader.py": "e7e13247c6ba135219b0ce9512e96c91dd26039167816af6b1f079dfcf3b673a",
    "task03_resource_path/workspace/test_template_loader.py": "23af044bfa8bbd132d2d514e7e9c426734d06fcb065df6bd61661bd549a97717",
    "task04_report_resources/task.json": "958684c7f290048869239989781b3ab031dec80217aaad73cca4c72683bf0ade",
    "task04_report_resources/workspace/report_renderer/__init__.py": "4d573efee6f8b89b77c1de27a425dad9e0074360c0727b289812ca33b24c46c8",
    "task04_report_resources/workspace/report_renderer/loader.py": "f1e76f65b2d57f1ec38392e32083a8b902ce49e2bcfc528c2ea06edf3daa410a",
    "task04_report_resources/workspace/report_renderer/renderer.py": "ab677a68abd489c1e954fd61e787704f6d5cabbc60c7f6bc3e4ded4bc857b8c1",
    "task04_report_resources/workspace/report_renderer/resources/defaults.json": "379261651c53495b43a6a3a5fd39257c4f5452ab988ab5e3a2f42b91269607c8",
    "task04_report_resources/workspace/test_report_renderer.py": "1dff6d665a813ab4ca4710c413655a4026e22a832fe7bc6cf8ee633f92bd61cd",
}


def copied_tools(tmp_path: Path) -> WorkspaceTools:
    workspace = tmp_path / "workspace"
    shutil.copytree(TASK_DIR / "workspace", workspace)
    return WorkspaceTools(workspace, TEST_COMMAND)


def successful_experience() -> ExperienceRecord:
    patch = """--- a/user_registry.py
+++ b/user_registry.py
@@ -1 +1 @@
-        key = identifier
+        key = identifier.strip().casefold()
"""
    return ExperienceRecord(
        experience_id="exp_task05_fixture",
        task_id=TASK_ID,
        producer_model="verified-fixture",
        problem=json.loads((TASK_DIR / "task.json").read_text())["description"],
        environment={"language": "python"},
        files_changed=["user_registry.py"],
        patch=patch,
        verification=Verification(command=TEST_COMMAND, passed=6, failed=0),
        successful=True,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        created_at="2026-01-01T00:00:01+00:00",
    )


def test_task05_loads_and_pristine_evaluator_has_expected_mixed_state(tmp_path):
    task = load_task(REPO_ROOT, TASK_ID)
    result = copied_tools(tmp_path).run_tests()

    assert task["test_command"] == TEST_COMMAND
    assert result.returncode == 1
    assert "3 failed, 3 passed" in result.stdout


def test_identifier_contract_and_invalid_input_cases_are_well_defined(tmp_path):
    tools = copied_tools(tmp_path)
    passing = tools.run_command(
        [
            "python", "-m", "pytest", "-q",
            "test_user_registry.py::test_exact_identifier_lookup_works",
            "test_user_registry.py::test_invalid_identifiers_remain_rejected",
            "test_user_registry.py::test_registration_return_values_and_length_are_preserved",
        ]
    )
    normalization = tools.run_command(
        [
            "python", "-m", "pytest", "-q",
            "test_user_registry.py::test_surrounding_whitespace_is_ignored",
            "test_user_registry.py::test_identifier_casing_is_ignored",
            "test_user_registry.py::test_equivalent_identifiers_do_not_create_duplicate_users",
        ]
    )

    assert passing.returncode == 0 and "3 passed" in passing.stdout
    assert normalization.returncode == 1 and "3 failed" in normalization.stdout


def test_task05_has_no_path_cwd_or_resource_concepts():
    task_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TASK_DIR.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    ).lower()
    for forbidden in (
        "__file__", "current working directory", "filesystem", "file path",
        "resource loading", "packaged file", "config loading",
    ):
        assert forbidden not in task_text


def test_recipe_and_transfer_compile_deterministically_without_patch_leakage():
    experience = successful_experience()
    first_recipe = compile_recipe(experience)
    second_recipe = compile_recipe(experience)
    transfer = compile_transfer_knowledge(first_recipe)
    serialized = json.dumps(transfer.to_dict(), sort_keys=True).lower()

    assert first_recipe == second_recipe
    assert first_recipe.task_type == "identifier_normalization"
    assert transfer.principles == [
        "Externally supplied identifiers should be normalized consistently "
        "before equality comparison or persistence when the contract defines "
        "equivalent textual forms."
    ]
    assert transfer.implementation_concepts == [
        "Apply identifier normalization at the input boundary while preserving "
        "existing validation behavior."
    ]
    assert experience.patch.lower() not in serialized
    for forbidden in (
        "user_registry.py", "__file__", "cwd", "current working directory",
        "filesystem", "path", "resource", "report_renderer", "loader.py",
        "defaults.json", "task02", "task03", "task04", "unified diff",
    ):
        assert forbidden not in serialized


def test_tasks_01_through_04_are_unchanged():
    for relative_path, expected_hash in PRIOR_TASK_HASHES.items():
        content = (REPO_ROOT / "tasks" / relative_path).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_hash
