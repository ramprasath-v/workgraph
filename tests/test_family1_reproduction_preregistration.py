import hashlib
import json
from pathlib import Path

from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter
from reproductions.family1_v1.preregistration import build_preregistration


REPO_ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION = (
    REPO_ROOT / "reproductions" / "family1_v1" / "preregistration.json"
)
TRANSFER = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_a4142b399f8684e6a75fda4a625ed4d8.json"
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


def test_preregistration_is_deterministic_and_matches_frozen_artifact():
    frozen = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    first = build_preregistration(REPO_ROOT)
    second = build_preregistration(REPO_ROOT)

    assert first == second == frozen
    assert frozen["evidence_status"] == (
        "new_retained_evidence_reproduction_not_original_recovery"
    )


def test_task04_and_exact_relevant_transfer_are_unchanged():
    frozen = build_preregistration(REPO_ROOT)

    assert frozen["frozen_inputs"]["task_hash"] == (
        "f8bd943eabc383371a17af7de97e83ec6850f43d9686b7b7454fa58742d6f91d"
    )
    assert _tree_hash(REPO_ROOT / "tasks" / "task04_report_resources") == (
        "f8bd943eabc383371a17af7de97e83ec6850f43d9686b7b7454fa58742d6f91d"
    )
    transfer = frozen["frozen_inputs"]["transfer"]
    assert transfer["transfer_knowledge_id"] == (
        "transfer_a4142b399f8684e6a75fda4a625ed4d8"
    )
    assert transfer["sha256"] == (
        "3f75b116a400961ee5897bdc5f72e01bec1579034d4718b578a0d426a5290587"
    )
    assert hashlib.sha256(TRANSFER.read_bytes()).hexdigest() == transfer["sha256"]


def test_transfer_provenance_is_unambiguous_verified_task02_chain():
    frozen = build_preregistration(REPO_ROOT)["frozen_inputs"]["transfer"]
    serialized = TRANSFER.read_text(encoding="utf-8").lower()

    assert frozen["source_recipe_id"] == (
        "recipe_98832e7c414d8cb42300e4dbc80d7535"
    )
    assert frozen["source_experience_id"] == (
        "exp_aedf873f3b13471ea3e0145e4a4c7c2d"
    )
    assert frozen["source_experience_verified"] is True
    for forbidden in (
        "task04",
        "report_renderer",
        "load_render_defaults",
        "render_report",
        "defaults.json",
        "--- a/",
        "+++ b/",
        "@@ -",
    ):
        assert forbidden not in serialized


def test_exactly_two_conditions_have_frozen_order_budget_and_repetitions():
    frozen = build_preregistration(REPO_ROOT)
    conditions = frozen["conditions_in_execution_order"]

    assert [value["condition_id"] for value in conditions] == [
        "F1R_BASELINE",
        "F1R_RELEVANT_TRANSFER",
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
        "transfer_knowledge/transfer_a4142b399f8684e6a75fda4a625ed4d8.json",
    ]


def test_historical_result_is_not_reconstructed_as_new_evidence():
    frozen = build_preregistration(REPO_ROOT)

    assert frozen["historical_observation"] == {
        "baseline_successes": 0,
        "relevant_transfer_successes": 5,
        "repetitions": 5,
        "machine_recomputed": False,
        "original_raw_evidence_retained": False,
    }
    assert not (
        REPO_ROOT / "reproductions" / "family1_v1" / "evidence_manifest.json"
    ).exists()
    assert not list(
        (REPO_ROOT / "reproductions" / "family1_v1").glob("*run-*.json")
    )


def test_existing_results_and_assistance_artifacts_are_unchanged_preexecution():
    expected = {
        "results": "a8fb5853898e0f486c11c44a1f4aed64a10f94afc8023c0bd7fc0108801a50f9",
        "experiences": "77cc9dcce5e35b3f091fe76c1d239ef465d54bc925ed177db67d33f7eec40f2c",
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
    expected_task_hashes = {
        "task10_booking_boundaries": "9d1d06ef163e57505c10f6e4ec54526cfcc14d6d7ff838e5f251a05731b8f56d",
        "task11_notification_retries": "612abef01526dc094fd78a2ce199d2b2edc66d5e1af2845a06c41add223339db",
        "task12_discounted_tax": "eed4fcb03bb615b890b2783285ea673a0d9f96326258510bb19fad20b15debb0",
    }
    for task_id, expected_hash in expected_task_hashes.items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash
    expected_files = {
        "preregistrations/family4_policy_v0_1.json": "8b9cf3e0f3e933c662ab1e7c310ffe525cd8c7c545e6f7025f6605a460c09695",
        "preregistrations/family4_execution_manifest_v0_1.json": "bc9883c30ab9b997ebec21537e61025636b58ce08731850463876801b92c63d1",
    }
    for relative, expected_hash in expected_files.items():
        assert hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest() == (
            expected_hash
        )


def test_preregistration_makes_no_model_or_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("reproduction preregistration must not call a provider")

    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    assert build_preregistration(REPO_ROOT)["reproduction_id"] == (
        "f1r_task04_core_v1"
    )
