import hashlib
import json
import shutil
from pathlib import Path

import pytest

from harness.models import AgentContext, MockModelAdapter, ModelAdapter, ModelResponse
from harness.prompting import build_model_prompt
from harness.runner import load_task, run_benchmark, run_repeated_benchmark
from harness.tools import ToolError, WorkspaceTools
from recipe.schema import load_recipe
from scout.runner import (
    GeneratedHandoff,
    ReadOnlyScoutTools,
    _without_evaluator_internals,
    run_scout,
)
from scout.schema import ScoutHandoff, load_scout_handoff
from transfer.schema import load_transfer_knowledge


REPO_ROOT = Path(__file__).resolve().parents[1]


def sample_handoff(task_id: str = "task01_exact") -> ScoutHandoff:
    return ScoutHandoff.create(
        task_id=task_id,
        producer_provider="vertex",
        producer_model="gemini-2.5-flash",
        observations=["The arithmetic implementation does not match its contract."],
        suspected_area="calculator.py division behavior",
        recommended_investigation=["Inspect the division implementation."],
        constraints=["Preserve the public function signature."],
        files_inspected=["calculator.py"],
        tool_calls=2,
        input_tokens=100,
        output_tokens=20,
        total_tokens=130,
        elapsed_seconds=1.25,
        created_at="2026-01-01T00:00:00+00:00",
    )


class InspectingModel(ModelAdapter):
    name = "scout-model"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        actions = (
            {"action": "list_files"},
            {"action": "read_file", "path": "report_renderer/loader.py"},
            {
                "action": "write_file",
                "path": "report_renderer/loader.py",
                "content": "forbidden mutation",
            },
            {"action": "read_file", "path": "report_renderer/renderer.py"},
            {"action": "finish"},
        )
        return ModelResponse(actions[min(len(context.history), len(actions) - 1)], 5, 1)


class StubHandoffGenerator:
    def generate_handoff(self, prompt: str) -> GeneratedHandoff:
        assert "report_renderer/loader.py" in prompt
        assert "forbidden mutation" in prompt
        return GeneratedHandoff(
            {
                "observations": [
                    "The renderer delegates bundled defaults lookup to a loader helper."
                ],
                "suspected_area": "Bundled-default location construction in the loader helper.",
                "recommended_investigation": [
                    "Compare default lookup behavior across execution directories."
                ],
                "constraints": [
                    "Preserve caller-supplied resource-directory behavior."
                ],
            },
            input_tokens=30,
            output_tokens=10,
            total_tokens=40,
        )


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_read_only_scout_lists_reads_rejects_writes_and_preserves_workspace(tmp_path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task04_report_resources",
        tmp_path / "tasks" / "task04_report_resources",
    )
    source = tmp_path / "tasks" / "task04_report_resources" / "workspace"
    before = _tree_hash(source)
    task = load_task(tmp_path, "task04_report_resources")

    handoff, path = run_scout(
        tmp_path,
        "task04_report_resources",
        task,
        InspectingModel(),
        StubHandoffGenerator(),
        max_steps=5,
    )

    assert before == _tree_hash(source)
    assert before == _tree_hash(tmp_path / ".workspaces" / "task04_report_resources-scout")
    assert handoff.files_inspected == [
        "report_renderer/loader.py",
        "report_renderer/renderer.py",
    ]
    assert handoff.tool_calls == 3
    assert handoff.input_tokens == 55
    assert handoff.output_tokens == 15
    assert handoff.total_tokens == 70
    assert load_scout_handoff(path) == handoff


def test_read_only_tools_never_expose_mutating_actions(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "source.py"
    source.write_text("ORIGINAL\n", encoding="utf-8")
    tools = ReadOnlyScoutTools(WorkspaceTools(workspace, ["pytest", "-q"]))

    assert tools.execute_action({"action": "list_files"}) == ["source.py"]
    assert tools.execute_action({"action": "read_file", "path": "source.py"}) == "ORIGINAL\n"
    with pytest.raises(ToolError, match="not allowed for a read-only scout"):
        tools.execute_action(
            {"action": "write_file", "path": "source.py", "content": "CHANGED\n"}
        )
    assert source.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_handoff_schema_rejects_patch_code_block_and_multiline_source():
    base = sample_handoff().to_dict()
    for leaked in ("--- a/source.py", "```python", "line one\nline two"):
        invalid = dict(base)
        invalid["observations"] = [leaked]
        with pytest.raises(ValueError):
            ScoutHandoff.from_dict(invalid)


def test_evaluator_identifiers_are_removed_from_generated_handoff_fields():
    values = [
        "The loader uses a relative bundled-resource location.",
        "test_relocated_execution fails under pytest.",
    ]

    assert _without_evaluator_internals(values) == [values[0]]


def test_scout_handoff_reaches_agent_and_records_separate_metrics(tmp_path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )
    handoff = sample_handoff()
    prompt = build_model_prompt(
        AgentContext(
            task_id="task01_exact",
            task_description="Fix division",
            available_tools=WorkspaceTools.ACTIONS,
            prior_experience=handoff.to_dict(),
        )
    )
    result, result_path = run_benchmark(
        tmp_path,
        "task01_exact",
        MockModelAdapter(),
        scout_handoff=handoff,
        run_id="scout-context",
    )

    assert "CURRENT-TASK SCOUT HANDOFF" in prompt
    assert "This is guidance only" in prompt
    assert result.context_mode == "scout_handoff"
    assert result.scout_handoff_id == handoff.scout_handoff_id
    assert result.scout_model == "gemini-2.5-flash"
    assert result.scout_input_tokens == 100
    assert result.scout_output_tokens == 20
    assert result.scout_total_tokens == 130
    assert result.scout_elapsed_seconds == 1.25
    assert result.input_tokens == 0
    assert result.total_inference_tokens() == result.total_tokens + 130
    assert result.total_inference_elapsed_seconds() == round(
        result.elapsed_seconds + 1.25, 6
    )
    persisted = json.loads(result_path.read_text(encoding="utf-8"))
    assert persisted["total_tokens"] == result.total_tokens
    assert persisted["total_inference_tokens"] == result.total_tokens + 130


def test_repeat_preserves_scout_identity_and_total_cost_accounting(tmp_path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )
    handoff = sample_handoff()
    summary, _ = run_repeated_benchmark(
        tmp_path,
        "task01_exact",
        MockModelAdapter(),
        repeat=2,
        scout_handoff=handoff,
        max_steps=8,
    )

    assert summary.context_mode == "scout_handoff"
    assert summary.scout_handoff_id == handoff.scout_handoff_id
    assert summary.scout_input_tokens == 100
    assert summary.scout_output_tokens == 20
    assert summary.scout_total_tokens == 130
    assert summary.average_total_inference_tokens == summary.average_total_tokens + 130
    assert summary.average_total_inference_elapsed_seconds == round(
        summary.average_elapsed_seconds + 1.25, 6
    )


def test_existing_context_rendering_and_artifacts_are_unchanged():
    transfer = load_transfer_knowledge(
        REPO_ROOT
        / "transfer_knowledge"
        / "transfer_a4142b399f8684e6a75fda4a625ed4d8.json"
    )
    recipe = load_recipe(
        REPO_ROOT / "recipes" / "recipe_98832e7c414d8cb42300e4dbc80d7535.json"
    )
    transfer_prompt = build_model_prompt(
        AgentContext(
            task_id="task03_resource_path",
            task_description="Fix loading",
            available_tools=WorkspaceTools.ACTIONS,
            prior_experience=transfer.to_dict(),
        )
    )
    recipe_prompt = build_model_prompt(
        AgentContext(
            task_id="task02_config_path",
            task_description="Fix config",
            available_tools=WorkspaceTools.ACTIONS,
            prior_experience=recipe.to_dict(),
        )
    )

    assert "PRIOR VERIFIED TRANSFER KNOWLEDGE" in transfer_prompt
    assert "CURRENT-TASK SCOUT HANDOFF" not in transfer_prompt
    assert "PRIOR VERIFIED EXPERIENCE" in recipe_prompt
    assert "CURRENT-TASK SCOUT HANDOFF" not in recipe_prompt


def test_tasks_01_through_05_remain_unchanged():
    expected = {
        "task04_report_resources/task.json": "958684c7f290048869239989781b3ab031dec80217aaad73cca4c72683bf0ade",
        "task04_report_resources/workspace/report_renderer/loader.py": "f1e76f65b2d57f1ec38392e32083a8b902ce49e2bcfc528c2ea06edf3daa410a",
        "task05_identifier_normalization/task.json": "c0d05dc303b7011970ed7876a568ba175a18489447a709f172cc9b5a1c39f6a2",
        "task05_identifier_normalization/workspace/user_registry.py": "6ec54867752d2edadf518ee3f9e7d47ad6f1df79bf4b1e45f5dd41aef18746c1",
        "task05_identifier_normalization/workspace/test_user_registry.py": "f640f19ce0a00c9e682be940dd0cf51ad1aba55a761d41b0821a265faf772739",
    }
    for relative, digest in expected.items():
        assert hashlib.sha256((REPO_ROOT / "tasks" / relative).read_bytes()).hexdigest() == digest
