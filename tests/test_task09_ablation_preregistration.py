import hashlib
import json
from pathlib import Path

from harness.assistance_control import load_assistance_control
from harness.models import AgentContext
from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.prompting import build_model_prompt
from harness.tools import WorkspaceTools
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter
from reproductions.family3_task09_ablation_v1.preregistration import (
    CONTROL_PATHS,
    build_preregistration,
)


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "reproductions/family3_task09_ablation_v1/preregistration.json"


def _tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_preregistration_is_deterministic_and_matches_frozen_json():
    frozen = json.loads(PREREG.read_text(encoding="utf-8"))
    assert build_preregistration(ROOT) == build_preregistration(ROOT) == frozen
    assert frozen["status"] == "preregistered_not_executed"


def test_exact_three_controls_order_budget_and_integrity_declaration():
    frozen = build_preregistration(ROOT)
    conditions = frozen["conditions_in_execution_order"]
    assert [condition["condition_id"] for condition in conditions] == [
        "EMPTY_ASSISTANCE_WRAPPER",
        "NEUTRAL_LENGTH_MATCHED_CONTEXT",
        "RELEVANT_PRINCIPLE_NO_AUTHORITY",
    ]
    for condition in conditions:
        assert condition["protected_evaluator_files"] == ["test_role_index.py"]
        command = condition["command"]
        assert command[command.index("--max-steps") + 1] == "8"
        assert command[command.index("--repeat") + 1] == "5"
        assert command[-2] == "--assistance-control"
    assert frozen["verification_integrity"]["guard_version"] == "1.0"


def test_payloads_have_frozen_sizes_match_and_no_task09_leakage():
    controls = [load_assistance_control(ROOT / path) for path in CONTROL_PATHS]
    assert [(item.payload_character_count, item.payload_approximate_tokens) for item in controls] == [
        (26, 7), (240, 60), (240, 60)
    ]
    assert controls[1].payload_character_count == controls[2].payload_character_count
    serialized = "\n".join(control.payload for control in controls).lower()
    for forbidden in (
        "task09", "test_role_index", "membership_registry", "role_index.py",
        "analysis_contract", "change_role", "role_summary",
    ):
        assert forbidden not in serialized
    for forbidden in (
        "verified experience", "prior successful execution", "previous agent",
        "source recipe", "trusted guidance",
    ):
        assert forbidden not in controls[2].payload.lower()


def test_prompt_template_and_position_are_constant_except_payload():
    task = json.loads((ROOT / "tasks/task09_role_changes/task.json").read_text())
    prompts = []
    controls = [load_assistance_control(ROOT / path) for path in CONTROL_PATHS]
    for control in controls:
        context = AgentContext(
            task_id="task09_role_changes",
            task_description=task["description"],
            available_tools=WorkspaceTools.ACTIONS,
            prior_experience=control.to_dict(),
            current_step=1,
            max_steps=8,
        )
        prompt = build_model_prompt(context)
        assert "analysis_contract" not in prompt
        assert "pristine_tests_passed" not in prompt
        assert prompt.count(control.payload) == 1
        prompts.append(prompt.replace(control.payload, "<PAYLOAD>"))
    assert prompts[0] == prompts[1] == prompts[2]


def test_frozen_task_evidence_assistance_family4_and_policy_are_unchanged():
    assert _tree_hash(ROOT / "tasks/task09_role_changes") == "c46bfd946da1242b031af87c3419686022ed43560d261bd15733a6ad7c33b437"
    assert _tree_hash(ROOT / "results") == "a1cb4d3e1fe1c875c6f119810a9afd34211183a7449c0c9e2af810d7e941b231"
    assert _tree_hash(ROOT / "experiences") == "d6da9257e231c6f1e6bfaa92869ea11cfc454092cb87d9495b385a55c832bd81"
    assert _tree_hash(ROOT / "policy") == "1403f90ebeeb47b6c6d43079569fd203c3ca082b004448c6b2d3117818ad691a"
    assert _tree_hash(ROOT / "preregistrations") == "f3bb2be74ee5536f76a311d9677f4b2852f1846e94d5da3654de4c07c11d650f"
    assert _tree_hash(ROOT / "transfer_knowledge") == "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f"
    assert _tree_hash(ROOT / "scout_handoffs") == "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62"
    assert _tree_hash(ROOT / "compact_scouts") == "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770"
    assert _tree_hash(ROOT / "reproductions/family1_v1") == "06cb5594dde90f955a022b5918a0b473de1b50343aaa6ece834db86f7c4522e5"
    assert _tree_hash(ROOT / "reproductions/family2_v1") == "565b20b9fe2986ad90c6efe71611ddd9acca2c1f24820b4ec558b660860cddcb"
    assert json.loads((ROOT / "reproductions/family1_v1/evidence_manifest.json").read_text())["classification"]["value"] == "FULL_REPRODUCTION"
    assert json.loads((ROOT / "reproductions/family2_v1/evidence_manifest.json").read_text())["classification"]["value"] == "NON_REPRODUCTION"
    for task, expected in {
        "task10_booking_boundaries": "9d1d06ef163e57505c10f6e4ec54526cfcc14d6d7ff838e5f251a05731b8f56d",
        "task11_notification_retries": "612abef01526dc094fd78a2ce199d2b2edc66d5e1af2845a06c41add223339db",
        "task12_discounted_tax": "eed4fcb03bb615b890b2783285ea673a0d9f96326258510bb19fad20b15debb0",
    }.items():
        assert _tree_hash(ROOT / "tasks" / task) == expected


def test_preregistration_calls_no_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("preregistration must not call a provider")

    for adapter in (VertexGeminiAdapter, TransformersModelAdapter, OpenAIModelAdapter, OllamaModelAdapter):
        monkeypatch.setattr(adapter, "generate_action", forbidden)
    assert build_preregistration(ROOT)["ablation_id"] == "family3_task09_assistance_interference_v1"
