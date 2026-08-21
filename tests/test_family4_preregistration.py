import hashlib
import json
import re
import shutil
from pathlib import Path

from family4.preregistration import build_preregistration, evaluate_policy_cases
from harness.models import AgentContext
from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.prompting import build_model_prompt
from harness.runner import load_task
from harness.tools import WorkspaceTools
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter


REPO_ROOT = Path(__file__).resolve().parents[1]
FAMILY4_IDS = (
    "task10_booking_boundaries",
    "task11_notification_retries",
    "task12_discounted_tax",
)
PREREGISTRATION = (
    REPO_ROOT / "preregistrations" / "family4_policy_v0_1.json"
)
FREEZE_MANIFEST = REPO_ROOT / "family4" / "freeze_manifest.json"


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


def _counts(output: str) -> tuple[int, int]:
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    return int(passed.group(1)), int(failed.group(1))


def test_exactly_three_family4_tasks_exist():
    actual = tuple(
        path.name
        for path in sorted((REPO_ROOT / "tasks").glob("task1[0-9]_*"))
        if path.is_dir()
    )

    assert actual == FAMILY4_IDS


def test_pristine_evaluators_have_predeclared_mixed_results(tmp_path):
    for task_id in FAMILY4_IDS:
        task = load_task(REPO_ROOT, task_id)
        workspace = tmp_path / task_id
        shutil.copytree(REPO_ROOT / "tasks" / task_id / "workspace", workspace)

        result = WorkspaceTools(workspace, task["test_command"]).run_tests()

        assert result.returncode == 1
        assert _counts(result.stdout) == (4, 2)
        assert task["analysis_contract"]["pristine_tests_passed"] == 4
        assert task["analysis_contract"]["pristine_tests_failed"] == 2


def test_policy_spec_and_package_are_unchanged():
    assert hashlib.sha256(
        (REPO_ROOT / "policy" / "policy_v0_1.json").read_bytes()
    ).hexdigest() == (
        "8d936bb727ad5acbdf54b4d62f950b06682452c5dfac7825595eb111c3bf58c7"
    )
    assert _tree_hash(REPO_ROOT / "policy") == (
        "1403f90ebeeb47b6c6d43079569fd203c3ca082b004448c6b2d3117818ad691a"
    )


def test_policy_preregistration_is_reproducible_and_matches_frozen_artifact():
    frozen = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    first = build_preregistration(REPO_ROOT)
    second = build_preregistration(REPO_ROOT)

    assert first == second == frozen
    assert [case["policy_output"]["decision"] for case in frozen["cases"]] == [
        "NO_ASSISTANCE",
        "NO_ASSISTANCE",
        "ESCALATE",
    ]


def test_policy_evaluation_reads_no_results_or_hidden_evaluator_data(monkeypatch):
    original_read_text = Path.read_text
    original_read_bytes = Path.read_bytes

    def guarded_read_text(path, *args, **kwargs):
        if (
            "results" in path.parts
            or path.name == "task.json"
            or path.name.startswith("test_")
        ):
            raise AssertionError("policy evaluation read a forbidden input")
        return original_read_text(path, *args, **kwargs)

    def guarded_read_bytes(path, *args, **kwargs):
        if (
            "results" in path.parts
            or path.name == "task.json"
            or path.name.startswith("test_")
        ):
            raise AssertionError("policy evaluation read a forbidden input")
        return original_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    assert len(evaluate_policy_cases(REPO_ROOT)) == 3


def test_analysis_contract_and_stratum_are_not_model_visible():
    metadata = json.loads(
        (REPO_ROOT / "family4" / "public_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    for case in metadata["cases"]:
        task = load_task(REPO_ROOT, case["task_id"])
        prompt = build_model_prompt(
            AgentContext(
                task_id=task["task_id"],
                task_description=task["description"],
                available_tools=WorkspaceTools.ACTIONS,
            )
        )
        assert task["description"] == case["public_task_description"]
        for forbidden in (
            "analysis_contract",
            "relevant_source_files",
            "allowed_output_files",
            "pristine_tests_passed",
            "pristine_tests_failed",
            '"stratum"',
            "capability_tier",
        ):
            assert forbidden not in prompt


def test_family4_tasks_contain_no_prior_outcomes_or_assistance_artifacts():
    task_text = "\n".join(
        path.read_text(encoding="utf-8")
        for task_id in FAMILY4_IDS
        for path in sorted((REPO_ROOT / "tasks" / task_id).rglob("*"))
        if path.is_file()
    ).lower()
    for forbidden in (
        "success rate",
        "baseline",
        "benchmark outcome",
        "qwen/qwen",
        "gemini-2.5",
        "transfer_knowledge_id",
        "scout_handoff_id",
        "expected patch",
        "family 1",
        "family 2",
        "family 3",
        "family 4",
    ):
        assert forbidden not in task_text
    for directory in (
        "experiences",
        "recipes",
        "transfer_knowledge",
        "scout_handoffs",
        "compact_scouts",
        "results",
    ):
        for path in (REPO_ROOT / directory).glob("*.json"):
            artifact = path.read_text(encoding="utf-8").lower()
            assert all(task_id not in artifact for task_id in FAMILY4_IDS)


def test_family4_tasks_match_hashes_frozen_before_policy_output():
    manifest = json.loads(FREEZE_MANIFEST.read_text(encoding="utf-8"))

    for task_id, expected_hash in manifest["family4_task_hashes"].items():
        assert _tree_hash(REPO_ROOT / "tasks" / task_id) == expected_hash


def test_tasks_01_through_09_remain_byte_for_byte_frozen():
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


def test_prior_artifacts_results_and_analysis_remain_frozen():
    expected_trees = {
        "experiences": "d6da9257e231c6f1e6bfaa92869ea11cfc454092cb87d9495b385a55c832bd81",
        "recipes": "65126b6652aff3ef87564efa601d94512cb456cd55a39d1befdeb4fbf4518eac",
        "transfer_knowledge": "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f",
        "scout_handoffs": "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62",
        "compact_scouts": "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770",
        "results": "a1cb4d3e1fe1c875c6f119810a9afd34211183a7449c0c9e2af810d7e941b231",
    }
    expected_files = {
            "analysis/cross_family_checkpoint.json": "bac8dd7671bfdc8812eaf34aab820bf8f0bbb17b9cbc44c71f32592e9a77b03c",
            "analysis/cross_family_manifest.json": "fb337e125eae381915c1045ab58ae0a022dca3b5b803d10d4b1fb99cec14bbce",
        "analysis/trajectory_metrics.py": "8f0e67fb1fcf166b769d0de102664eaf1aae61a6aea41dbaeff6a2091362c741",
    }
    for directory, expected_hash in expected_trees.items():
        assert _tree_hash(REPO_ROOT / directory) == expected_hash
    for relative, expected_hash in expected_files.items():
        assert hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest() == (
            expected_hash
        )


def test_policy_preregistration_makes_no_model_or_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Family 4 preregistration must not call a provider")

    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    assert len(build_preregistration(REPO_ROOT)["cases"]) == 3
