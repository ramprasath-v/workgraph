import hashlib
import json
import shutil
from pathlib import Path

from harness.models import AgentContext
from harness.prompting import build_model_prompt
from harness.runner import load_task
from harness.tools import WorkspaceTools


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK08_ID = "task08_catalog_updates"
TASK09_ID = "task09_role_changes"
TASK08 = REPO_ROOT / "tasks" / TASK08_ID
TASK09 = REPO_ROOT / "tasks" / TASK09_ID


def _tree_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    ).lower()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and ".pytest_cache" not in path.parts
        ):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _copied_tools(tmp_path: Path, task_dir: Path) -> WorkspaceTools:
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    workspace = tmp_path / task["task_id"]
    shutil.copytree(task_dir / "workspace", workspace)
    return WorkspaceTools(workspace, task["test_command"])


def test_family3_tasks_load_and_have_exact_pristine_evaluator_shape(tmp_path):
    task08 = load_task(REPO_ROOT, TASK08_ID)
    task09 = load_task(REPO_ROOT, TASK09_ID)
    result08 = _copied_tools(tmp_path, TASK08).run_tests()
    result09 = _copied_tools(tmp_path, TASK09).run_tests()

    assert task08["test_command"][-1] == "test_catalog.py"
    assert task09["test_command"][-1] == "test_role_index.py"
    assert result08.returncode == result09.returncode == 1
    assert "2 failed, 4 passed" in result08.stdout
    assert "2 failed, 4 passed" in result09.stdout


def test_family3_tasks_are_cross_task_and_prior_family_distinct():
    task08_text = _tree_text(TASK08)
    task09_text = _tree_text(TASK09)

    for forbidden in (
        "task09",
        "membership_registry",
        "role_index",
        "member",
        "editor",
        "reviewer",
        "viewer",
    ):
        assert forbidden not in task08_text
    for forbidden in (
        "task08",
        "productcatalog",
        "catalog.py",
        "notebook",
        "price_cents",
        "display_price",
    ):
        assert forbidden not in task09_text
    for text in (task08_text, task09_text):
        for forbidden in (
            "__file__",
            "current working directory",
            "cwd",
            "filesystem",
            "resource loading",
            "bundled resource",
            "report_renderer",
            "defaults.json",
            "retry",
            "idempoten",
            "duplicate delivery",
            "replay",
            "webhook",
            "shipment",
            "payment event",
        ):
            assert forbidden not in text


def test_public_problem_statements_do_not_reveal_implementation_fix():
    descriptions = [
        json.loads((task / "task.json").read_text(encoding="utf-8"))["description"]
        for task in (TASK08, TASK09)
    ]

    assert descriptions == [
        "Catalog price updates are accepted and visible through direct price "
        "lookups, but customer-facing catalog views can continue showing earlier "
        "values. Correct this inconsistency while preserving validation, update "
        "return values, initial formatting, and the existing public API.",
        "Team role changes are accepted and visible through direct membership "
        "lookups, but role-based views can continue reporting the previous "
        "assignment. Correct this inconsistency while preserving validation, "
        "change return values, initial summaries, and the existing public API.",
    ]
    for description in descriptions:
        lowered = description.lower()
        for forbidden in (
            "_display_prices",
            "_members_by_role",
            "_build_index",
            "cache variable",
            "invalidate",
            "rebuild",
            "expected patch",
            "write_file",
        ):
            assert forbidden not in lowered


def test_task09_analysis_contract_is_predeclared_and_not_prompt_visible():
    task = load_task(REPO_ROOT, TASK09_ID)
    expected_contract = {
        "relevant_source_files": ["membership_registry.py", "role_index.py"],
        "allowed_output_files": ["membership_registry.py", "role_index.py"],
        "pristine_tests_passed": 4,
        "pristine_tests_failed": 2,
    }

    assert task["analysis_contract"] == expected_contract
    prompt = build_model_prompt(
        AgentContext(
            task_id=task["task_id"],
            task_description=task["description"],
            available_tools=WorkspaceTools.ACTIONS,
        )
    )

    assert "analysis_contract" not in prompt
    assert "relevant_source_files" not in prompt
    assert "allowed_output_files" not in prompt
    assert "pristine_tests_passed" not in prompt
    assert "membership_registry.py" not in prompt
    assert "role_index.py" not in prompt


def test_task09_has_only_the_authorized_scout_artifacts():
    prohibited_artifact_directories = (
        "results",
        "experiences",
        "recipes",
        "transfer_knowledge",
    )
    for directory in prohibited_artifact_directories:
        for path in (REPO_ROOT / directory).glob("*.json"):
            assert TASK09_ID not in path.name
            assert TASK09_ID not in path.read_text(encoding="utf-8")
    task09_scouts = []
    for path in (REPO_ROOT / "scout_handoffs").glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("task_id") == TASK09_ID:
            task09_scouts.append(path.name)
    assert task09_scouts == [
        "scout_ed6739707d4474f82577cd4d5da3c82b.json"
    ]
    task09_compacts = []
    for path in (REPO_ROOT / "compact_scouts").glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("source_scout_handoff_id") == (
            "scout_ed6739707d4474f82577cd4d5da3c82b"
        ):
            task09_compacts.append(path.name)
    assert task09_compacts == [
        "compact_scout_2dafc6a6e899b8423c3c76376f9a0dfb.json"
    ]


def test_tasks_01_through_09_remain_frozen():
    expected = {
        "task01_exact": "b7c9cc3f8ad64c4a58aa039b540552b22797291225a297b08650f042d708aaa3",
        "task02_config_path": "de523163cd0bcba766f34ebe7d8f39d3d1dd67050ef496f658d4ad5544b6d56d",
        "task03_resource_path": "ce29a013d68169ffd20ab3e9fb626161c7c05dbf76eeea0b176484bd58e96f44",
        "task04_report_resources": "f8bd943eabc383371a17af7de97e83ec6850f43d9686b7b7454fa58742d6f91d",
        "task05_identifier_normalization": "72b04b3d69327da57e6cbfc1960e5319fba07d92bff5aa66f4d643efe3b7cb1c",
        "task06_retry_idempotency": "f56ba98316423c1a9617763711ec548adb1eb2353b2ce5d261b8a34fa975083d",
        "task07_retry_transfer": "c66e566fe8cc84b4cffa880fcce9ef66db1fc5368bccf9f5278571adf82eb619",
        "task08_catalog_updates": "c272d3f3a9128e0fe3d836af908f65d037cd15f500412e3fd96522777d66d74a",
        "task09_role_changes": "c46bfd946da1242b031af87c3419686022ed43560d261bd15733a6ad7c33b437",
    }
    for task_id, expected_hash in expected.items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash


def test_current_artifacts_and_frozen_analysis_are_frozen():
    expected = {
        "experiences": "77cc9dcce5e35b3f091fe76c1d239ef465d54bc925ed177db67d33f7eec40f2c",
        "recipes": "65126b6652aff3ef87564efa601d94512cb456cd55a39d1befdeb4fbf4518eac",
        "transfer_knowledge": "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f",
        "scout_handoffs": "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62",
        "compact_scouts": "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770",
        "results": "15680c57bd26e79a614b0f0d5c026fba0766803843d7ca606d07a624296c611b",
        "analysis": "b15c10e72549ee6b73bcd79894acfbfbcc5104d58047628793e325869226f9be",
    }
    for directory, expected_hash in expected.items():
        assert _tree_hash(REPO_ROOT / directory) == expected_hash
