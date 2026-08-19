import hashlib
import json
import shutil
from pathlib import Path

from experience.schema import ExperienceRecord, Verification
from harness.runner import load_task
from harness.tools import WorkspaceTools
from recipe.compiler import compile_recipe
from recipe.schema import load_recipe
from transfer.compiler import compile_transfer_knowledge
from transfer.schema import load_transfer_knowledge


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK06 = REPO_ROOT / "tasks" / "task06_retry_idempotency"
TASK07 = REPO_ROOT / "tasks" / "task07_retry_transfer"


def _copied_tools(tmp_path: Path, task_dir: Path) -> WorkspaceTools:
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    workspace = tmp_path / task["task_id"]
    shutil.copytree(task_dir / "workspace", workspace)
    return WorkspaceTools(workspace, task["test_command"])


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


def _successful_task06_experience() -> ExperienceRecord:
    patch = """--- a/payment_processor.py
+++ b/payment_processor.py
@@ -1 +1 @@
-        self.total_charged += numeric_amount
+        if event_id in self.completed_results: return self.completed_results[event_id]
"""
    return ExperienceRecord(
        experience_id="exp_task06_fixture",
        task_id="task06_retry_idempotency",
        producer_model="verified-fixture",
        problem=json.loads((TASK06 / "task.json").read_text())["description"],
        environment={"language": "python"},
        files_changed=["payment_processor.py"],
        patch=patch,
        verification=Verification(
            command=["python", "-m", "pytest", "-q", "test_payment_processor.py"],
            passed=6,
            failed=0,
        ),
        successful=True,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        created_at="2026-01-01T00:00:01+00:00",
    )


def test_task06_and_task07_load_and_have_deterministic_mixed_pristine_state(
    tmp_path,
):
    task06 = load_task(REPO_ROOT, "task06_retry_idempotency")
    task07 = load_task(REPO_ROOT, "task07_retry_transfer")
    result06 = _copied_tools(tmp_path, TASK06).run_tests()
    result07 = _copied_tools(tmp_path, TASK07).run_tests()

    assert task06["test_command"][-1] == "test_payment_processor.py"
    assert task07["test_command"][-1] == "test_delivery_receiver.py"
    assert result06.returncode == result07.returncode == 1
    assert "2 failed, 4 passed" in result06.stdout
    assert "2 failed, 4 passed" in result07.stdout


def test_retry_family_tasks_are_distinct_and_exclude_prior_family_concepts():
    task06_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TASK06.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    ).lower()
    task07_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(TASK07.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    ).lower()

    for forbidden in (
        "task07",
        "delivery_receiver",
        "shipment",
        "webhook",
        "order_number",
        "tracking_number",
        "delivery_token",
    ):
        assert forbidden not in task06_text
    for forbidden in (
        "task06",
        "payment",
        "event_id",
        "payment_processor",
        "total_charged",
        "charge_count",
    ):
        assert forbidden not in task07_text
    for text in (task06_text, task07_text):
        for forbidden in (
            "__file__",
            "current working directory",
            "cwd",
            "resource loading",
            "bundled resource",
            "config/settings",
            "report_renderer",
        ):
            assert forbidden not in text


def test_task06_recipe_and_transfer_are_deterministic_and_generalized(tmp_path):
    experience = _successful_task06_experience()
    first_recipe = compile_recipe(experience)
    second_recipe = compile_recipe(experience)
    first_transfer = compile_transfer_knowledge(first_recipe)
    second_transfer = compile_transfer_knowledge(second_recipe)
    recipe_path = first_recipe.write_json(tmp_path / "recipes")
    transfer_path = first_transfer.write_json(tmp_path / "transfer_knowledge")
    serialized = json.dumps(first_transfer.to_dict(), sort_keys=True).lower()

    assert first_recipe == second_recipe
    assert first_transfer == second_transfer
    assert first_recipe.task_type == "retry_idempotency"
    assert load_recipe(recipe_path) == first_recipe
    assert load_transfer_knowledge(transfer_path) == first_transfer
    assert "logical operation" in serialized
    assert "side effect" in serialized
    assert "recorded outcome" in serialized
    assert experience.patch.lower() not in serialized
    for forbidden in (
        "payment_processor.py",
        "paymentprocessor",
        "payment",
        "event_id",
        "evt-",
        "delivery_receiver.py",
        "deliveryreceiver",
        "shipment",
        "webhook",
        "order_number",
        "tracking_number",
        "delivery_token",
        "task07",
        "--- a/",
        "+++ b/",
        "@@ -",
        "test_",
    ):
        assert forbidden not in serialized


def test_task05_irrelevant_transfer_has_no_retry_or_idempotency_guidance():
    path = (
        REPO_ROOT
        / "transfer_knowledge"
        / "transfer_56c07e702add42b7a04b9c7f7a4a7230.json"
    )
    serialized = path.read_text(encoding="utf-8").lower()
    for forbidden in (
        "retry",
        "idempoten",
        "duplicate",
        "side effect",
        "delivery",
        "logical operation",
    ):
        assert forbidden not in serialized


def test_tasks_01_through_05_and_frozen_task04_artifacts_are_unchanged():
    expected_task_hashes = {
        "task01_exact": "b7c9cc3f8ad64c4a58aa039b540552b22797291225a297b08650f042d708aaa3",
        "task02_config_path": "de523163cd0bcba766f34ebe7d8f39d3d1dd67050ef496f658d4ad5544b6d56d",
        "task03_resource_path": "ce29a013d68169ffd20ab3e9fb626161c7c05dbf76eeea0b176484bd58e96f44",
        "task04_report_resources": "f8bd943eabc383371a17af7de97e83ec6850f43d9686b7b7454fa58742d6f91d",
        "task05_identifier_normalization": "72b04b3d69327da57e6cbfc1960e5319fba07d92bff5aa66f4d643efe3b7cb1c",
    }
    for task_id, expected_hash in expected_task_hashes.items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash

    expected_artifacts = {
        "transfer_knowledge/transfer_a4142b399f8684e6a75fda4a625ed4d8.json": "3f75b116a400961ee5897bdc5f72e01bec1579034d4718b578a0d426a5290587",
        "transfer_knowledge/transfer_56c07e702add42b7a04b9c7f7a4a7230.json": "9f210e3e275109035cb7e9e8ce482b2f7f55f55c9c439be542946e05d5fb260c",
        "scout_handoffs/scout_78cdb2504c4636ff8b007f24762e2f9f.json": "b55b0282060442dd1db1db19aa38d58e891882e88a53a5c5a48651ef0d8bca5a",
        "compact_scouts/compact_scout_0f1e06290913286e9e5bb9c5ab4b1f83.json": "4730bab5147556ac5ab3661120916077739d918dfb5ea9420b66c04cea1c1df5",
    }
    for relative, expected_hash in expected_artifacts.items():
        assert hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest() == expected_hash
