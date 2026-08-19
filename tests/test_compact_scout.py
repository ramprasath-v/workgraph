import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from compact_scout.compiler import compile_compact_scout
from compact_scout.schema import load_compact_scout
from harness.models import AgentContext, ModelAdapter, ModelResponse
from harness.prompting import build_model_prompt, format_scout_handoff
from harness.runner import main, run_benchmark
from harness.tools import WorkspaceTools
from harness.vertex_adapter import VertexGeminiAdapter
from scout.schema import load_scout_handoff


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    REPO_ROOT
    / "scout_handoffs"
    / "scout_78cdb2504c4636ff8b007f24762e2f9f.json"
)
TASK02_TRANSFER = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_a4142b399f8684e6a75fda4a625ed4d8.json"
)
TASK05_TRANSFER = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_56c07e702add42b7a04b9c7f7a4a7230.json"
)


class FinishOnlyModel(ModelAdapter):
    name = "finish-only"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        return ModelResponse({"action": "finish"}, input_tokens=7, output_tokens=2)


def test_compilation_is_deterministic_uses_exact_source_and_makes_no_model_call(
    monkeypatch,
):
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert source_hash == "b55b0282060442dd1db1db19aa38d58e891882e88a53a5c5a48651ef0d8bca5a"
    handoff = load_scout_handoff(SOURCE)

    def forbidden_model_call(*args, **kwargs):
        raise AssertionError("compact compilation must not call a model")

    monkeypatch.setattr(VertexGeminiAdapter, "generate_action", forbidden_model_call)
    first = compile_compact_scout(handoff)
    second = compile_compact_scout(handoff)

    assert first == second
    assert first.source_scout_handoff_id == (
        "scout_78cdb2504c4636ff8b007f24762e2f9f"
    )
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash


def test_compact_guidance_is_supported_and_removes_current_task_details():
    handoff = load_scout_handoff(SOURCE)
    compact = compile_compact_scout(handoff)
    serialized = json.dumps(compact.to_dict(), sort_keys=True)
    guidance = json.dumps(
        {
            "principles": compact.principles,
            "implementation_concepts": compact.implementation_concepts,
        },
        sort_keys=True,
    )

    assert "working directory" in guidance
    assert "package-relative" in guidance
    assert "caller-provided location overrides" in guidance
    assert "existing output behavior" in guidance
    for forbidden in (
        "report_renderer",
        "loader.py",
        "renderer.py",
        "defaults.json",
        "_defaults_path",
        "load_render_defaults",
        "test_",
        "Path(\"",
        "importlib.resources.files",
        "__file__",
        "--- a/",
        "+++ b/",
        "@@ -",
        "```",
    ):
        assert forbidden not in guidance
    assert handoff.scout_handoff_id in serialized
    assert handoff.producer_model == compact.scout_model
    assert handoff.total_tokens == compact.scout_total_tokens


def test_missing_source_evidence_is_rejected_without_inventing_advice():
    handoff = load_scout_handoff(SOURCE)
    data = handoff.to_dict()
    data["observations"] = ["A component was inspected."]
    data["suspected_area"] = "An unspecified component."
    data["recommended_investigation"] = ["Inspect the component."]
    data["constraints"] = ["Preserve behavior."]

    with pytest.raises(ValueError, match="lacks supported compacting evidence"):
        compile_compact_scout(type(handoff).from_dict(data))


def test_compact_schema_round_trip_and_cli(tmp_path, monkeypatch, capsys):
    compact = compile_compact_scout(load_scout_handoff(SOURCE))
    path = compact.write_json(tmp_path / "manual")
    assert load_compact_scout(path) == compact

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness.runner",
            "--root",
            str(tmp_path),
            "--compile-compact-scout",
            str(SOURCE),
        ],
    )
    assert main() == 0
    outputs = list((tmp_path / "compact_scouts").glob("compact_scout_*.json"))
    assert len(outputs) == 1
    assert load_compact_scout(outputs[0]) == compact
    assert f"compact_scout={outputs[0]}" in capsys.readouterr().out


def test_compact_prompt_and_result_provenance_keep_scout_cost_separate(tmp_path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task04_report_resources",
        tmp_path / "tasks" / "task04_report_resources",
    )
    compact = compile_compact_scout(load_scout_handoff(SOURCE))
    prompt = build_model_prompt(
        AgentContext(
            task_id="task04_report_resources",
            task_description="Fix report rendering.",
            available_tools=WorkspaceTools.ACTIONS,
            prior_experience=compact.to_dict(),
        )
    )
    result, _ = run_benchmark(
        tmp_path,
        "task04_report_resources",
        FinishOnlyModel(),
        compact_scout=compact,
        max_steps=1,
    )

    assert "COMPACT CURRENT-TASK SCOUT KNOWLEDGE" in prompt
    assert "A read-only scout inspected this current task" in prompt
    assert "gemini" not in prompt.lower()
    assert "Choose ONLY the next single tool action." in prompt
    assert result.context_mode == "compact_scout"
    assert result.source_scout_handoff_id == compact.source_scout_handoff_id
    assert result.compact_scout_id == compact.compact_scout_id
    assert result.scout_model == compact.scout_model
    assert result.scout_total_tokens == compact.scout_total_tokens
    assert result.total_tokens == 9
    assert result.total_inference_tokens() == compact.scout_total_tokens + 9
    assert result.scout_accounting_mode == "frozen_handoff_amortized"


def test_existing_artifacts_and_detailed_scout_rendering_remain_unchanged():
    expected_hashes = {
        SOURCE: "b55b0282060442dd1db1db19aa38d58e891882e88a53a5c5a48651ef0d8bca5a",
        TASK02_TRANSFER: "3f75b116a400961ee5897bdc5f72e01bec1579034d4718b578a0d426a5290587",
        TASK05_TRANSFER: "9f210e3e275109035cb7e9e8ce482b2f7f55f55c9c439be542946e05d5fb260c",
    }
    for path, expected_hash in expected_hashes.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash

    detailed = load_scout_handoff(SOURCE)
    rendered = format_scout_handoff(detailed.to_dict())
    assert "CURRENT-TASK SCOUT HANDOFF" in rendered
    assert "report_renderer/loader.py" in rendered
    assert "COMPACT CURRENT-TASK SCOUT KNOWLEDGE" not in rendered


def test_tasks_01_through_05_have_no_control3_changes():
    expected = {
        "task01_exact/task.json": "75dbf2309b5c022c6cf640f040cbbf1b81cad0928494671c1ce102fbdab613d4",
        "task02_config_path/task.json": "45d90ae98d9f9c1710a93bd53abadead4a5a8744d6705506eeb58f0f85cd98a0",
        "task03_resource_path/task.json": "3cd3c4a7d8a572b1f897056af3e609af49bd491e7e7e1d0739b2fde6658f6148",
        "task04_report_resources/task.json": "958684c7f290048869239989781b3ab031dec80217aaad73cca4c72683bf0ade",
        "task05_identifier_normalization/task.json": "c0d05dc303b7011970ed7876a568ba175a18489447a709f172cc9b5a1c39f6a2",
    }
    for relative, expected_hash in expected.items():
        path = REPO_ROOT / "tasks" / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
