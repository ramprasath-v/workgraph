import hashlib
import json
from pathlib import Path

from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter
from reproductions.family2_v1.preregistration import build_preregistration


REPO_ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    REPO_ROOT / "reproductions" / "family2_v1" / "preregistration.json"
)
TRANSFER = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_93a42588ddd62085a6289d9b12613079.json"
)


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


def test_family2_preregistration_is_deterministic_and_matches_frozen_artifact():
    frozen = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    assert build_preregistration(REPO_ROOT) == build_preregistration(REPO_ROOT)
    assert build_preregistration(REPO_ROOT) == frozen
    assert frozen["evidence_status"] == (
        "new_retained_evidence_reproduction_not_original_recovery"
    )


def test_task07_and_exact_task06_transfer_are_frozen():
    frozen = build_preregistration(REPO_ROOT)

    assert frozen["frozen_inputs"]["task_hash"] == (
        "c66e566fe8cc84b4cffa880fcce9ef66db1fc5368bccf9f5278571adf82eb619"
    )
    assert _tree_hash(REPO_ROOT / "tasks" / "task07_retry_transfer") == (
        "c66e566fe8cc84b4cffa880fcce9ef66db1fc5368bccf9f5278571adf82eb619"
    )
    transfer = frozen["frozen_inputs"]["transfer"]
    assert transfer["transfer_knowledge_id"] == (
        "transfer_93a42588ddd62085a6289d9b12613079"
    )
    assert transfer["sha256"] == (
        "83b26d53a73b764f8670f447d9c56cd6295e88d15027fc50a6d22b8a6d214933"
    )
    assert hashlib.sha256(TRANSFER.read_bytes()).hexdigest() == transfer["sha256"]


def test_transfer_has_verified_task06_provenance_and_no_task07_leakage():
    transfer = build_preregistration(REPO_ROOT)["frozen_inputs"]["transfer"]
    serialized = TRANSFER.read_text(encoding="utf-8").lower()

    assert transfer["source_recipe_id"] == (
        "recipe_da7d5db67724045643eb513a5c8192e4"
    )
    assert transfer["source_experience_id"] == (
        "exp_101aa9645ab34d46ad1d3fbf4f7dcae7"
    )
    assert transfer["source_experience_verified"] is True
    for forbidden in (
        "task07",
        "delivery_receiver.py",
        "shipment_service.py",
        "deliveryreceiver",
        "createshipment",
        "tracking_number",
        "test_redelivery",
        "--- a/",
        "+++ b/",
        "@@ -",
    ):
        assert forbidden not in serialized


def test_exactly_two_conditions_have_frozen_order_budget_and_repetitions():
    frozen = build_preregistration(REPO_ROOT)
    conditions = frozen["conditions_in_execution_order"]

    assert [condition["condition_id"] for condition in conditions] == [
        "F2R_BASELINE",
        "F2R_RELEVANT_TRANSFER",
    ]
    assert frozen["target"]["max_steps"] == 8
    assert frozen["target"]["repetitions"] == 5
    for condition in conditions:
        command = condition["command"]
        assert command[command.index("--max-steps") + 1] == "8"
        assert command[command.index("--repeat") + 1] == "5"
    assert "--transfer-knowledge" not in conditions[0]["command"]
    assert conditions[1]["command"][-2:] == [
        "--transfer-knowledge",
        "transfer_knowledge/transfer_93a42588ddd62085a6289d9b12613079.json",
    ]


def test_historical_results_are_not_reconstructed_and_manifest_is_postexecution():
    historical = build_preregistration(REPO_ROOT)["historical_observation"]

    assert historical["baseline_successes"] == 0
    assert historical["relevant_transfer_successes"] == 0
    assert historical["machine_recomputed"] is False
    assert historical["original_raw_evidence_retained"] is False
    assert (
        REPO_ROOT / "reproductions" / "family2_v1" / "evidence_manifest.json"
    ).exists()


def test_family1_reproduction_and_previous_artifacts_are_unchanged():
    assert hashlib.sha256(
        (REPO_ROOT / "reproductions/family1_v1/preregistration.json").read_bytes()
    ).hexdigest() == "9d38cbe9f56ff7864714d0e81bb6c28fdfb21206e59d56708a64c78d3d9049c9"
    expected = {
        "results": "a1cb4d3e1fe1c875c6f119810a9afd34211183a7449c0c9e2af810d7e941b231",
        "experiences": "d6da9257e231c6f1e6bfaa92869ea11cfc454092cb87d9495b385a55c832bd81",
        "recipes": "65126b6652aff3ef87564efa601d94512cb456cd55a39d1befdeb4fbf4518eac",
        "transfer_knowledge": "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f",
        "scout_handoffs": "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62",
        "compact_scouts": "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770",
    }
    for directory, expected_hash in expected.items():
        assert _tree_hash(REPO_ROOT / directory) == expected_hash


def test_policy_and_family4_remain_untouched():
    assert _tree_hash(REPO_ROOT / "policy") == (
        "1403f90ebeeb47b6c6d43079569fd203c3ca082b004448c6b2d3117818ad691a"
    )
    expected_tasks = {
        "task10_booking_boundaries": "9d1d06ef163e57505c10f6e4ec54526cfcc14d6d7ff838e5f251a05731b8f56d",
        "task11_notification_retries": "612abef01526dc094fd78a2ce199d2b2edc66d5e1af2845a06c41add223339db",
        "task12_discounted_tax": "eed4fcb03bb615b890b2783285ea673a0d9f96326258510bb19fad20b15debb0",
    }
    for task_id, expected_hash in expected_tasks.items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash
    expected_files = {
        "preregistrations/family4_policy_v0_1.json": "8b9cf3e0f3e933c662ab1e7c310ffe525cd8c7c545e6f7025f6605a460c09695",
        "preregistrations/family4_execution_manifest_v0_1.json": "bc9883c30ab9b997ebec21537e61025636b58ce08731850463876801b92c63d1",
    }
    for relative, expected_hash in expected_files.items():
        assert hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest() == (
            expected_hash
        )


def test_preregistration_reads_no_results_and_calls_no_provider(monkeypatch):
    original_read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        if "results" in Path(path).parts:
            raise AssertionError("preregistration must not read benchmark results")
        return original_read_text(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("reproduction preregistration must not call a provider")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    assert build_preregistration(REPO_ROOT)["reproduction_id"] == (
        "f2r_task07_core_v1"
    )
