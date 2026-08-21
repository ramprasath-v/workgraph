import hashlib
import json
from pathlib import Path

from analysis.reproduction_evidence import build_evidence_manifest
from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter


ROOT = Path(__file__).resolve().parents[1]


def _paths_hash(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_manifests_are_deterministically_derived_from_retained_raw_files():
    for family, relative in (
        ("family_1", "reproductions/family1_v1/evidence_manifest.json"),
        ("family_2", "reproductions/family2_v1/evidence_manifest.json"),
    ):
        frozen = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert build_evidence_manifest(ROOT, family) == frozen
        assert build_evidence_manifest(ROOT, family) == build_evidence_manifest(ROOT, family)


def test_original_reproduction_results_and_generated_experiences_are_unchanged():
    family_1 = [
        path for aggregate in ("28b2a9415bb0", "729e34487d81")
        for path in ROOT.glob(f"results/repeat_task04_report_resources_{aggregate}*.json")
    ]
    family_2 = [
        path for aggregate in ("769cbddc39d9", "f0c2446e7222")
        for path in ROOT.glob(f"results/repeat_task07_retry_transfer_{aggregate}*.json")
    ]
    assert _paths_hash(family_1) == "6eb518a42b28ef4863b27adf9e14d4e928c88cf93db0ee011c32fa5bda3be781"
    assert _paths_hash(family_2) == "09c1e130b7c4f8463acec87477155d663d9ce6cecce6f7904a2ce785d53ef080"
    assert _tree_hash(ROOT / "experiences") == "d6da9257e231c6f1e6bfaa92869ea11cfc454092cb87d9495b385a55c832bd81"


def test_classifications_follow_frozen_rules_and_integrity_is_explicit():
    family_1 = build_evidence_manifest(ROOT, "family_1")
    family_2 = build_evidence_manifest(ROOT, "family_2")

    assert family_1["classification"]["value"] == "FULL_REPRODUCTION"
    assert family_1["integrity_findings"]["test_file_write_detected"] is False
    assert family_2["classification"]["value"] == "NON_REPRODUCTION"
    assisted = family_2["conditions"][1]
    assert assisted["outcome"]["successful_runs"] == 5
    assert assisted["outcome"]["final_tests_passed"] == [1] * 5
    assert assisted["directly_measured_file_behavior"]["test_file_written_run_count"] == 5
    assert "test_delivery_receiver.py" in assisted["directly_measured_file_behavior"]["unique_files_written"]


def test_family3_family4_policy_and_preregistrations_are_frozen():
    family_3 = list(ROOT.glob("results/repeat_task09_role_changes_*.json"))
    assert _paths_hash(family_3) == "735556474d51805b0bc4f24f75e0c694be4a20db317c800795b80cc4a9919a75"
    assert _tree_hash(ROOT / "tasks" / "task09_role_changes") == "c46bfd946da1242b031af87c3419686022ed43560d261bd15733a6ad7c33b437"
    assert _tree_hash(ROOT / "policy") == "1403f90ebeeb47b6c6d43079569fd203c3ca082b004448c6b2d3117818ad691a"
    assert _tree_hash(ROOT / "preregistrations") == "f3bb2be74ee5536f76a311d9677f4b2852f1846e94d5da3654de4c07c11d650f"
    for task, expected in {
        "task10_booking_boundaries": "9d1d06ef163e57505c10f6e4ec54526cfcc14d6d7ff838e5f251a05731b8f56d",
        "task11_notification_retries": "612abef01526dc094fd78a2ce199d2b2edc66d5e1af2845a06c41add223339db",
        "task12_discounted_tax": "eed4fcb03bb615b890b2783285ea673a0d9f96326258510bb19fad20b15debb0",
    }.items():
        assert _tree_hash(ROOT / "tasks" / task) == expected
    assert hashlib.sha256((ROOT / "reproductions/family1_v1/preregistration.json").read_bytes()).hexdigest() == "9d38cbe9f56ff7864714d0e81bb6c28fdfb21206e59d56708a64c78d3d9049c9"
    assert hashlib.sha256((ROOT / "reproductions/family2_v1/preregistration.json").read_bytes()).hexdigest() == "033773271cbf78417743d47a36c109e5f288c845d35417e054110e96753f00e5"


def test_offline_ingestion_calls_no_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline evidence ingestion must not call a provider")

    for adapter in (VertexGeminiAdapter, TransformersModelAdapter, OpenAIModelAdapter, OllamaModelAdapter):
        monkeypatch.setattr(adapter, "generate_action", forbidden)
    assert build_evidence_manifest(ROOT, "family_1")["family_id"] == "family_1"
    assert build_evidence_manifest(ROOT, "family_2")["family_id"] == "family_2"
