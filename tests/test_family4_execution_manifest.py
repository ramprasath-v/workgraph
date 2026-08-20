import hashlib
import json
from pathlib import Path

from family4.compact_protocol import (
    COMPILER_VERSION,
    compile_family4_compact_scout,
)
from family4.execution_manifest import build_execution_manifest
from harness.models import AgentContext
from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.prompting import build_model_prompt
from harness.runner import load_task
from harness.tools import WorkspaceTools
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter
from scout.schema import ScoutHandoff


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    REPO_ROOT / "preregistrations" / "family4_execution_manifest_v0_1.json"
)
PREREGISTRATION = (
    REPO_ROOT / "preregistrations" / "family4_policy_v0_1.json"
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


def _scout_fixture() -> ScoutHandoff:
    return ScoutHandoff.from_dict(
        {
            "scout_handoff_version": "0.1",
            "scout_handoff_id": "scout_family4_fixture",
            "task_id": "synthetic_public_task",
            "producer_provider": "vertex",
            "producer_model": "gemini-2.5-flash",
            "observations": [
                "booking_calendar.py rejects adjacent intervals in test_boundary_case."
            ],
            "suspected_area": "The overlaps_existing decision treats a shared boundary as occupied.",
            "recommended_investigation": [
                "Review overlaps_existing(start_minute) while preserving validation."
            ],
            "constraints": ["Preserve ordering and public return values."],
            "files_inspected": ["booking_calendar.py", "test_booking_calendar.py"],
            "tool_calls": 3,
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "elapsed_seconds": 1.25,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )


def test_execution_manifest_is_deterministic_and_matches_artifact():
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))

    first = build_execution_manifest(REPO_ROOT)
    second = build_execution_manifest(REPO_ROOT)

    assert first == second == frozen
    assert frozen["manifest_version"] == "0.1"


def test_policy_and_family4_policy_preregistration_are_unchanged():
    assert _tree_hash(REPO_ROOT / "policy") == (
        "1403f90ebeeb47b6c6d43079569fd203c3ca082b004448c6b2d3117818ad691a"
    )
    assert hashlib.sha256(PREREGISTRATION.read_bytes()).hexdigest() == (
        "8b9cf3e0f3e933c662ab1e7c310ffe525cd8c7c545e6f7025f6605a460c09695"
    )


def test_tasks_01_through_12_remain_frozen():
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


def test_historical_transfer_selection_is_deterministic_and_pre_family4():
    manifest = build_execution_manifest(REPO_ROOT)
    selection = manifest["historical_transfer_selection"]

    assert selection["candidate_universe_frozen_before_family4"] is True
    assert {
        task_id: value["transfer_knowledge_id"]
        for task_id, value in selection["assignments"].items()
    } == {
        "task10_booking_boundaries": "transfer_56c07e702add42b7a04b9c7f7a4a7230",
        "task11_notification_retries": "transfer_93a42588ddd62085a6289d9b12613079",
        "task12_discounted_tax": "transfer_56c07e702add42b7a04b9c7f7a4a7230",
    }
    for assignment in selection["assignments"].values():
        assert assignment["existed_before_family4"] is True
        assert hashlib.sha256(
            (REPO_ROOT / assignment["artifact_path"]).read_bytes()
        ).hexdigest() == assignment["artifact_sha256"]
    assert _tree_hash(REPO_ROOT / "transfer_knowledge") == (
        "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f"
    )


def test_manifest_construction_reads_no_benchmark_results_or_hidden_task_data(
    monkeypatch,
):
    original_read_text = Path.read_text
    original_read_bytes = Path.read_bytes

    def guard(path: Path):
        if (
            "results" in path.parts
            or path.name == "task.json"
            or path.name.startswith("test_")
        ):
            raise AssertionError("execution manifest read a forbidden input")

    def guarded_text(path, *args, **kwargs):
        guard(path)
        return original_read_text(path, *args, **kwargs)

    def guarded_bytes(path, *args, **kwargs):
        guard(path)
        return original_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_text)
    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)

    assert build_execution_manifest(REPO_ROOT)["manifest_version"] == "0.1"


def test_scout_protocol_excludes_historical_outcomes_and_mutation():
    protocol = build_execution_manifest(REPO_ROOT)["scout_acquisition_protocol"]

    assert protocol["read_only"] is True
    assert protocol["actions"] == ["list_files", "read_file", "run_tests"]
    assert protocol["count_per_task"] == 1
    forbidden = " ".join(protocol["forbidden_inputs"]).lower()
    assert "target outcomes" in forbidden
    assert "historical transfer" in forbidden
    assert "prior trajectories" in forbidden
    assert "analysis_contract" in forbidden


def test_compact_protocol_is_deterministic_generic_and_leakage_filtered():
    handoff = _scout_fixture()

    first = compile_family4_compact_scout(handoff)
    second = compile_family4_compact_scout(handoff)
    serialized = json.dumps(first.to_dict(), sort_keys=True).lower()

    assert first == second
    assert COMPILER_VERSION == "family4-generic-0.1"
    assert first.source_scout_handoff_id == handoff.scout_handoff_id
    for forbidden in (
        "booking_calendar.py",
        "test_booking_calendar.py",
        "test_boundary_case",
        "overlaps_existing",
        "start_minute",
        "```",
        "--- a/",
    ):
        assert forbidden not in serialized


def test_duplicate_aliases_are_exact_and_reference_valid_run_sets():
    manifest = build_execution_manifest(REPO_ROOT)
    aliases = manifest["strategy_run_set_aliases"]
    run_sets = manifest["unique_run_sets"]

    assert aliases["task10_booking_boundaries"]["POLICY_V0_1"] == aliases[
        "task10_booking_boundaries"
    ]["ALWAYS_NO_ASSISTANCE"]
    assert aliases["task11_notification_retries"]["POLICY_V0_1"] == aliases[
        "task11_notification_retries"
    ]["ALWAYS_NO_ASSISTANCE"]
    assert aliases["task12_discounted_tax"]["POLICY_V0_1"] == aliases[
        "task12_discounted_tax"
    ]["ALWAYS_ESCALATE"]
    assert all(
        run_set_id in run_sets
        for task_aliases in aliases.values()
        for run_set_id in task_aliases.values()
    )


def test_analysis_contract_remains_non_model_visible():
    for task_id in (
        "task10_booking_boundaries",
        "task11_notification_retries",
        "task12_discounted_tax",
    ):
        task = load_task(REPO_ROOT, task_id)
        prompt = build_model_prompt(
            AgentContext(
                task_id=task_id,
                task_description=task["description"],
                available_tools=WorkspaceTools.ACTIONS,
            )
        )
        for forbidden in (
            "analysis_contract",
            "relevant_source_files",
            "allowed_output_files",
            "pristine_tests_passed",
            "pristine_tests_failed",
        ):
            assert forbidden not in prompt


def test_manifest_construction_makes_no_model_or_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("manifest construction must not call a provider")

    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    assert len(build_execution_manifest(REPO_ROOT)["unique_run_sets"]) == 12


def test_no_family4_result_or_assistance_artifact_exists():
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
            text = path.read_text(encoding="utf-8")
            assert all(task_id not in text for task_id in family4_ids)
