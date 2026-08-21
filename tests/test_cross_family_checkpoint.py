import hashlib
import json
from pathlib import Path

import pytest

from analysis.cross_family_checkpoint import build_checkpoint
from analysis.trajectory_metrics import analyze_result_file
from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "analysis" / "cross_family_manifest.json"
CHECKPOINT = REPO_ROOT / "analysis" / "cross_family_checkpoint.json"
TASK09_CONDITIONS = {
    "baseline": "696038d25c92",
    "relevant_historical_transfer": "d826c0ae1567",
    "irrelevant_historical_transfer": "4e7bcf6529bb",
    "detailed_current_task_scout": "8af1270fb575",
    "compact_current_task_scout": "482e71e10fe0",
}


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


def _family(checkpoint, family_id):
    return next(
        family for family in checkpoint["families"]
        if family["family_id"] == family_id
    )


def _condition(checkpoint, condition_id):
    family = _family(checkpoint, "family_3")
    return next(
        condition for condition in family["conditions"]
        if condition["condition_id"] == condition_id
    )


def test_manifest_maps_every_condition_explicitly_without_globs():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert [family["family_id"] for family in manifest["families"]] == [
        "family_1", "family_2", "family_3"
    ]
    assert all(len(family["conditions"]) == 5 for family in manifest["families"])
    for family in manifest["families"][:2]:
        for condition in family["conditions"][:2]:
            assert condition["retention_status"] == "complete_raw_and_aggregate"
            assert len(condition["run_results"]) == 5
            assert (REPO_ROOT / condition["aggregate_result"]).is_file()
        for condition in family["conditions"][2:]:
            assert condition["retention_status"] == "raw_results_not_retained"
            assert condition["aggregate_result"] is None
            assert condition["run_results"] == []
    for condition in manifest["families"][2]["conditions"]:
        assert condition["retention_status"] == "complete_raw_and_aggregate"
        assert len(condition["run_results"]) == 5
        paths = [condition["aggregate_result"], *condition["run_results"]]
        assert all(not any(char in path for char in "*?[]") for path in paths)
        assert all((REPO_ROOT / path).is_file() for path in paths)


def test_checkpoint_is_deterministic_and_family3_outcomes_come_from_raw_json():
    first = build_checkpoint(REPO_ROOT, MANIFEST)
    second = build_checkpoint(REPO_ROOT, MANIFEST)

    assert first == second
    expected_successes = {
        "baseline": 5,
        "relevant_historical_transfer": 0,
        "irrelevant_historical_transfer": 0,
        "detailed_current_task_scout": 0,
        "compact_current_task_scout": 0,
    }
    for condition_id, aggregate_id in TASK09_CONDITIONS.items():
        condition = _condition(first, condition_id)
        raw_paths = sorted(
            REPO_ROOT.glob(
                f"results/repeat_task09_role_changes_{aggregate_id}-run-*.json"
            )
        )
        raw_successes = sum(
            json.loads(path.read_text(encoding="utf-8"))["success"]
            for path in raw_paths
        )
        assert len(raw_paths) == condition["outcome"]["total_runs"] == 5
        assert raw_successes == condition["outcome"]["successful_runs"]
        assert raw_successes == expected_successes[condition_id]


def test_family3_trajectory_metrics_are_frozen_and_contract_aware():
    checkpoint = build_checkpoint(REPO_ROOT, MANIFEST)
    expected = {
        "baseline": (6, 0, 1.0, 1.0, 0.0, 0),
        "relevant_historical_transfer": (0, 1, 1.0, 1.0, 1.0, 4),
        "irrelevant_historical_transfer": (4, 2, 1.0, 1.0, 0.0, 0),
        "detailed_current_task_scout": (0, 6, 1.0, 0.0, 0.0, 4),
        "compact_current_task_scout": (0, 6, 0.0, 1.0, 0.0, 4),
    }
    for condition_id, values in expected.items():
        metrics = _condition(checkpoint, condition_id)["trajectory_metrics"]
        assert (
            metrics["mean_final_tests_passed"],
            metrics["mean_final_tests_failed"],
            metrics["verification_use_rate"],
            metrics["relevant_source_read_rate"],
            metrics["unexpected_file_created_or_written_rate"],
            metrics["mean_passing_test_regression_count"],
        ) == values
        assert metrics["malformed_output_rate"] == 1.0


def test_qwen_only_and_total_inference_accounting_remain_distinct():
    checkpoint = build_checkpoint(REPO_ROOT, MANIFEST)
    detailed = _condition(checkpoint, "detailed_current_task_scout")
    compact = _condition(checkpoint, "compact_current_task_scout")

    assert detailed["qwen_only_efficiency"]["mean_total_tokens"] == 12369
    assert detailed["persisted_total_inference_accounting"] == {
        "average_total_inference_elapsed_seconds": 196.241585,
        "average_total_inference_tokens": 24557,
        "estimated_deployment_total_inference_elapsed_seconds": 981.207923,
        "estimated_deployment_total_inference_tokens": 122785,
        "frozen_experiment_total_inference_elapsed_seconds": 891.523319,
        "frozen_experiment_total_inference_tokens": 74033,
        "scout_elapsed_seconds": 22.421151,
        "scout_input_tokens": 9525,
        "scout_output_tokens": 570,
        "scout_total_tokens": 12188,
    }
    assert compact["qwen_only_efficiency"]["mean_total_tokens"] == 5499
    assert compact["persisted_total_inference_accounting"][
        "frozen_experiment_total_inference_tokens"
    ] == 39683


def test_task04_and_task07_core_reproductions_are_machine_derived():
    checkpoint = build_checkpoint(REPO_ROOT, MANIFEST)

    for family_id in ("family_1", "family_2"):
        family = _family(checkpoint, family_id)
        assert family["evidence_level"] == (
            "retained_core_reproduction_with_unretained_historical_conditions"
        )
        assert family["historical_observation"]["machine_derived"] is False
        for condition in family["conditions"][:2]:
            assert condition["evidence"] is not None
            assert condition["outcome"]["total_runs"] == 5
            assert condition["trajectory_metrics"] is not None
        for condition in family["conditions"][2:]:
            assert condition["evidence"] is None
            assert condition["outcome"] is None


def test_checkpoint_generation_makes_no_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline checkpoint must not call a model/provider")

    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    build_checkpoint(REPO_ROOT, MANIFEST)


def test_generated_checkpoint_matches_builder_and_inputs_are_read_only():
    before = _tree_hash(REPO_ROOT / "results")
    generated = json.loads(CHECKPOINT.read_text(encoding="utf-8"))

    assert generated == build_checkpoint(REPO_ROOT, MANIFEST)
    assert _tree_hash(REPO_ROOT / "results") == before


def test_manifest_identity_tampering_is_rejected(tmp_path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["families"][2]["conditions"][0]["expected_identity"][
        "context_mode"
    ] = "transfer_knowledge"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="identity mismatch"):
        build_checkpoint(REPO_ROOT, path)


def test_frozen_tasks_artifacts_results_and_analyzer_are_unchanged():
    expected_tasks = {
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
    expected_trees = {
        "experiences": "d6da9257e231c6f1e6bfaa92869ea11cfc454092cb87d9495b385a55c832bd81",
        "recipes": "65126b6652aff3ef87564efa601d94512cb456cd55a39d1befdeb4fbf4518eac",
        "transfer_knowledge": "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f",
        "scout_handoffs": "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62",
        "compact_scouts": "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770",
        "results": "a1cb4d3e1fe1c875c6f119810a9afd34211183a7449c0c9e2af810d7e941b231",
    }
    for task_id, expected_hash in expected_tasks.items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash
    for directory, expected_hash in expected_trees.items():
        assert _tree_hash(REPO_ROOT / directory) == expected_hash
    assert hashlib.sha256(
        (REPO_ROOT / "analysis" / "trajectory_metrics.py").read_bytes()
    ).hexdigest() == (
        "8f0e67fb1fcf166b769d0de102664eaf1aae61a6aea41dbaeff6a2091362c741"
    )
    assert hashlib.sha256(
        (REPO_ROOT / "docs" / "trajectory-measurement.md").read_bytes()
    ).hexdigest() == (
        "3fd11d52040f2fe76ff7620efcfcfa9b09054102169868edb9425246674acbfc"
    )


def test_existing_trajectory_analyzer_semantics_remain_usable():
    metrics = analyze_result_file(
        REPO_ROOT / "results" / "task06_retry_idempotency-4a67af377dc7.json"
    )

    assert metrics.final_success is True
    assert metrics.test_execution_count == 2
    assert metrics.revision_after_test_failure is True
    assert metrics.verification_after_revision is True
