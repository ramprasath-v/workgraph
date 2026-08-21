import hashlib
import json
from pathlib import Path

from analysis.paper_readiness import build_paper_evidence
from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "paper" / "evidence-summary.json"
CHECKPOINT = REPO_ROOT / "analysis" / "cross_family_checkpoint.json"


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


def test_paper_evidence_is_deterministic_and_matches_frozen_checkpoint_projection():
    frozen = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    first = build_paper_evidence(REPO_ROOT)
    second = build_paper_evidence(REPO_ROOT)

    assert first == second == frozen
    assert frozen["source_checkpoint_sha256"] == hashlib.sha256(
        CHECKPOINT.read_bytes()
    ).hexdigest()


def test_families_1_and_2_project_only_new_retained_reproductions():
    evidence = build_paper_evidence(REPO_ROOT)

    for family in evidence["families"][:2]:
        assert family["machine_derived"] is True
        assert family["raw_per_run_evidence_retained"] is True
        assert len(family["condition_metrics"]) == 2
        assert family["evidence_status"] == (
            "machine_derived_from_retained_raw_results"
        )
        assert family["historical_observation"]["machine_derived"] is False
        assert family["reproduction_evidence"]["sha256"]


def test_all_family3_numbers_are_projected_from_checkpoint():
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    evidence = build_paper_evidence(REPO_ROOT)
    source_conditions = checkpoint["families"][2]["conditions"]
    paper_conditions = evidence["families"][2]["condition_metrics"]

    assert evidence["families"][2]["machine_derived"] is True
    assert evidence["families"][2]["raw_per_run_evidence_retained"] is True
    assert len(source_conditions) == len(paper_conditions) == 5
    for source, projected in zip(source_conditions, paper_conditions):
        assert projected["condition_id"] == source["condition_id"]
        assert projected["outcome"] == source["outcome"]
        assert projected["target_model_efficiency"] == source[
            "qwen_only_efficiency"
        ]
        assert projected["total_inference_accounting"] == source[
            "persisted_total_inference_accounting"
        ]
        assert projected["trajectory_metrics"] == source["trajectory_metrics"]


def test_paper_docs_label_provenance_and_unevaluated_policy():
    readiness = (REPO_ROOT / "docs" / "paper-readiness.md").read_text(
        encoding="utf-8"
    ).lower()
    outline = (REPO_ROOT / "paper" / "outline.md").read_text(
        encoding="utf-8"
    ).lower()
    table = (REPO_ROOT / "paper" / "evidence-table.md").read_text(
        encoding="utf-8"
    ).lower()
    combined = readiness + outline + table

    assert "historical observation" in combined
    assert "raw per-run evidence retained: **yes**" in table
    assert "machine-derived" in combined
    assert "not yet been evaluated" in combined or "not evaluated" in combined
    assert "do not establish population-level" in combined
    assert "original task 04" in combined and "task 07" in combined


def test_family3_reported_anchor_values_match_frozen_machine_evidence():
    table = (REPO_ROOT / "paper" / "evidence-table.md").read_text(
        encoding="utf-8"
    )

    for expected in ("baseline **5/5**", "relevant", "0/5"):
        assert expected in table


def test_tasks_01_through_12_are_unchanged():
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
        "task10_booking_boundaries": "9d1d06ef163e57505c10f6e4ec54526cfcc14d6d7ff838e5f251a05731b8f56d",
        "task11_notification_retries": "612abef01526dc094fd78a2ce199d2b2edc66d5e1af2845a06c41add223339db",
        "task12_discounted_tax": "eed4fcb03bb615b890b2783285ea673a0d9f96326258510bb19fad20b15debb0",
    }
    for task_id, expected_hash in expected.items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash


def test_frozen_results_policy_preregistrations_and_artifacts_are_unchanged():
    expected_trees = {
        "results": "a1cb4d3e1fe1c875c6f119810a9afd34211183a7449c0c9e2af810d7e941b231",
        "policy": "1403f90ebeeb47b6c6d43079569fd203c3ca082b004448c6b2d3117818ad691a",
        "experiences": "d6da9257e231c6f1e6bfaa92869ea11cfc454092cb87d9495b385a55c832bd81",
        "recipes": "65126b6652aff3ef87564efa601d94512cb456cd55a39d1befdeb4fbf4518eac",
        "transfer_knowledge": "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f",
        "scout_handoffs": "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62",
        "compact_scouts": "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770",
    }
    expected_files = {
        "preregistrations/family4_policy_v0_1.json": "8b9cf3e0f3e933c662ab1e7c310ffe525cd8c7c545e6f7025f6605a460c09695",
        "preregistrations/family4_execution_manifest_v0_1.json": "bc9883c30ab9b997ebec21537e61025636b58ce08731850463876801b92c63d1",
    }
    for directory, expected_hash in expected_trees.items():
        assert _tree_hash(REPO_ROOT / directory) == expected_hash
    for relative, expected_hash in expected_files.items():
        assert hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest() == (
            expected_hash
        )


def test_no_family4_execution_or_new_assistance_artifact_exists():
    family4_ids = (
        "task10_booking_boundaries",
        "task11_notification_retries",
        "task12_discounted_tax",
    )
    for directory in (
        "results",
        "experiences",
        "recipes",
        "scout_handoffs",
        "compact_scouts",
    ):
        for path in (REPO_ROOT / directory).glob("*.json"):
            serialized = path.read_text(encoding="utf-8")
            assert all(task_id not in serialized for task_id in family4_ids)


def test_paper_readiness_generation_makes_no_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("paper-readiness review must not call a provider")

    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    assert build_paper_evidence(REPO_ROOT)["paper_evidence_version"] == "0.2"
