import argparse
import json
import shutil
from pathlib import Path

import pytest

from harness.models import AgentContext, MockModelAdapter, ModelAdapter, ModelResponse
from experience.schema import ExperienceRecord, Verification
from harness.runner import (
    _positive_int,
    load_task,
    run_benchmark,
    run_comparison,
    run_representation_comparison,
)
from harness.tools import WorkspaceTools
from recipe.schema import ExperienceRecipe, RecipeStep, RecipeVerification


REPO_ROOT = Path(__file__).resolve().parents[1]


class FinishOnlyModelAdapter(ModelAdapter):
    name = "finish-only"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        return ModelResponse({"action": "finish"})


class RepeatingReadModelAdapter(ModelAdapter):
    name = "repeating-read"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        return ModelResponse({"action": "read_file", "path": "calculator.py"})


def sample_experience() -> ExperienceRecord:
    return ExperienceRecord(
        experience_id="exp_prior",
        task_id="task01_exact",
        producer_model="mock",
        problem="Fix division",
        environment={"language": "python"},
        files_changed=["calculator.py"],
        patch="-    return a * b\n+    return a / b\n",
        verification=Verification(
            command=["python", "-m", "pytest", "-q", "test_calculator.py"],
            passed=3,
            failed=0,
        ),
        successful=True,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        created_at="2026-01-01T00:00:01+00:00",
    )


def sample_recipe() -> ExperienceRecipe:
    return ExperienceRecipe(
        recipe_version="0.1",
        recipe_id="recipe_prior",
        source_experience_id="exp_prior",
        task_id="task01_exact",
        task_type="arithmetic_fix",
        problem="Division uses multiplication.",
        target_files=["calculator.py"],
        steps=[
            RecipeStep(1, "Inspect calculator.py."),
            RecipeStep(2, "Correct division and run tests."),
        ],
        verification=RecipeVerification(3, 0),
    )


def test_load_task():
    task = load_task(REPO_ROOT, "task01_exact")
    assert task["task_id"] == "task01_exact"
    assert "divide function" in task["description"]


def test_original_task_fails_before_modification(tmp_path: Path):
    source = REPO_ROOT / "tasks" / "task01_exact" / "workspace"
    workspace = tmp_path / "workspace"
    shutil.copytree(source, workspace)
    result = WorkspaceTools(
        workspace,
        ["python", "-m", "pytest", "-q", "test_calculator.py"],
    ).run_tests()
    assert result.returncode != 0


def test_mock_model_completes_task_and_preserves_source(tmp_path: Path):
    task_source = REPO_ROOT / "tasks" / "task01_exact"
    shutil.copytree(task_source, tmp_path / "tasks" / "task01_exact")
    source_file = tmp_path / "tasks" / "task01_exact" / "workspace" / "calculator.py"
    original = source_file.read_text(encoding="utf-8")
    result, result_path = run_benchmark(
        tmp_path, "task01_exact", MockModelAdapter(), run_id="test-mock-run"
    )
    assert result.success is True
    assert result.tests_passed == 3
    assert result.tests_failed == 0
    assert result.model_provider == "mock"
    assert result.experience_used is False
    assert result.experience_id is None
    assert result.context_mode == "none"
    assert result.source_experience_id is None
    assert result.recipe_id is None
    assert result.failure_type is None
    assert result.max_steps == 20
    assert result.trajectory[0]["step"] == 1
    assert result.trajectory[0]["action"] == "list_files"
    assert result.trajectory[0]["target"] is None
    assert str(result.trajectory[0]["outcome"]).startswith("success (")
    assert result_path.exists()
    persisted_result = json.loads(result_path.read_text(encoding="utf-8"))
    assert persisted_result["trajectory"] == result.trajectory
    assert persisted_result["trajectory_diagnostics"] == (
        result.trajectory_diagnostics
    )
    assert "return a * b" not in json.dumps(result.trajectory)
    assert "return a / b" not in json.dumps(result.trajectory)
    assert result.generated_experience_id is not None
    assert result.generated_experience_path is not None
    experience_path = Path(result.generated_experience_path)
    assert experience_path.exists()
    experience = json.loads(experience_path.read_text(encoding="utf-8"))
    assert experience["files_changed"] == ["calculator.py"]
    assert "-    return a * b" in experience["patch"]
    assert "+    return a / b" in experience["patch"]
    assert source_file.read_text(encoding="utf-8") == original
    active = tmp_path / ".workspaces" / "task01_exact" / "calculator.py"
    assert "return a / b" in active.read_text(encoding="utf-8")


def test_failed_run_generates_no_experience(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )

    result, _ = run_benchmark(
        tmp_path, "task01_exact", FinishOnlyModelAdapter(), run_id="failed-run"
    )

    assert result.success is False
    assert result.generated_experience_id is None
    assert result.generated_experience_path is None
    assert not (tmp_path / "experiences").exists()


def test_runner_with_supplied_experience_sets_metrics(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )

    result, _ = run_benchmark(
        tmp_path,
        "task01_exact",
        MockModelAdapter(),
        run_id="with-experience",
        experience=sample_experience(),
    )

    assert result.success is True
    assert result.experience_used is True
    assert result.experience_id == "exp_prior"
    assert result.context_mode == "raw_experience"
    assert result.source_experience_id == "exp_prior"
    assert result.recipe_id is None


def test_runner_with_recipe_sets_context_metrics(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )

    result, _ = run_benchmark(
        tmp_path,
        "task01_exact",
        MockModelAdapter(),
        run_id="with-recipe",
        recipe=sample_recipe(),
    )

    assert result.success is True
    assert result.experience_used is True
    assert result.experience_id == "exp_prior"
    assert result.context_mode == "recipe"
    assert result.source_experience_id == "exp_prior"
    assert result.recipe_id == "recipe_prior"


def test_comparison_resets_workspace_for_both_runs(tmp_path: Path, monkeypatch):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )
    import harness.runner as runner_module

    original_reset = runner_module.reset_workspace
    reset_contents: list[str] = []

    def observed_reset(source: Path, target: Path) -> Path:
        workspace = original_reset(source, target)
        reset_contents.append(
            (workspace / "calculator.py").read_text(encoding="utf-8")
        )
        return workspace

    monkeypatch.setattr(runner_module, "reset_workspace", observed_reset)

    baseline, experiment = run_comparison(
        tmp_path, "task01_exact", MockModelAdapter(), sample_experience()
    )

    assert baseline.success and experiment.success
    assert len(reset_contents) == 2
    assert all("return a * b" in content for content in reset_contents)


def test_max_steps_parser_accepts_positive_and_rejects_non_positive():
    assert _positive_int("12") == 12
    with pytest.raises(argparse.ArgumentTypeError, match="positive integer"):
        _positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError, match="positive integer"):
        _positive_int("-2")
    with pytest.raises(argparse.ArgumentTypeError, match="positive integer"):
        _positive_int("abc")


def test_exhausted_step_budget_has_specific_failure(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )

    result, _ = run_benchmark(
        tmp_path,
        "task01_exact",
        RepeatingReadModelAdapter(),
        run_id="exhausted-run",
        max_steps=3,
    )

    assert result.success is False
    assert result.agent_steps == 3
    assert result.max_steps == 3
    assert result.failure_type == "max_steps_exhausted"
    assert result.failure_message == (
        "Agent did not complete the task within 3 steps."
    )
    assert result.trajectory_diagnostics["file_reads"] == 3
    assert result.trajectory_diagnostics["repeated_identical_actions"] == 2


def test_comparison_has_independent_trajectories_and_same_budget(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )

    baseline, experiment = run_comparison(
        tmp_path,
        "task01_exact",
        RepeatingReadModelAdapter(),
        sample_experience(),
        max_steps=2,
    )

    assert baseline.max_steps == experiment.max_steps == 2
    assert baseline.agent_steps == experiment.agent_steps == 2
    assert baseline.trajectory == experiment.trajectory
    assert baseline.trajectory is not experiment.trajectory
    assert baseline.failure_type == experiment.failure_type == (
        "max_steps_exhausted"
    )


def test_three_way_comparison_resets_each_context_independently(
    tmp_path: Path, monkeypatch
):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )
    import harness.runner as runner_module

    original_reset = runner_module.reset_workspace
    reset_contents: list[str] = []

    def observed_reset(source: Path, target: Path) -> Path:
        workspace = original_reset(source, target)
        reset_contents.append(
            (workspace / "calculator.py").read_text(encoding="utf-8")
        )
        return workspace

    monkeypatch.setattr(runner_module, "reset_workspace", observed_reset)

    baseline, raw, compact = run_representation_comparison(
        tmp_path,
        "task01_exact",
        MockModelAdapter(),
        sample_experience(),
        sample_recipe(),
        max_steps=12,
    )

    assert len(reset_contents) == 3
    assert all("return a * b" in content for content in reset_contents)
    assert [result.context_mode for result in (baseline, raw, compact)] == [
        "none",
        "raw_experience",
        "recipe",
    ]
    assert all(result.max_steps == 12 for result in (baseline, raw, compact))
    assert all(result.success for result in (baseline, raw, compact))
