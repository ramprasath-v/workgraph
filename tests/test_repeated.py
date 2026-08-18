import argparse
import json
import shutil
from pathlib import Path

import pytest

from harness.metrics import RunResult
from harness.models import MockModelAdapter
from harness.repeated import aggregate_results
from harness.runner import _repeat_count, run_repeated_benchmark
from recipe.schema import ExperienceRecipe, RecipeStep, RecipeVerification


REPO_ROOT = Path(__file__).resolve().parents[1]


def result(
    run_id: str,
    *,
    success: bool,
    steps: int,
    calls: int,
    input_tokens: int,
    output_tokens: int,
    elapsed: float,
    failure_type: str | None = None,
) -> RunResult:
    return RunResult(
        run_id=run_id,
        task_id="task",
        model_provider="test",
        model_name="model",
        experience_used=False,
        experience_id=None,
        success=success,
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-01-01T00:00:01+00:00",
        elapsed_seconds=elapsed,
        agent_steps=steps,
        tool_calls=calls,
        test_command=["pytest", "-q"],
        tests_passed=1 if success else 0,
        tests_failed=0 if success else 1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=0.0,
        max_steps=8,
        trajectory=[],
        trajectory_diagnostics={},
        failure_type=failure_type,
    )


def recipe() -> ExperienceRecipe:
    return ExperienceRecipe(
        recipe_version="0.2",
        recipe_id="recipe_repeat",
        source_experience_id="exp_repeat",
        task_id="task01_exact",
        task_type="arithmetic_fix",
        problem="Fix division.",
        target_files=["calculator.py"],
        steps=[
            RecipeStep(1, "Inspect calculator.py."),
            RecipeStep(2, "Preserve the function contract."),
            RecipeStep(3, "Correct the operation."),
        ],
        verification=RecipeVerification(3, 0),
        implementation_concepts=["Use the language's division operator."],
    )


def test_repeat_count_parsing_and_invalid_values():
    assert _repeat_count("5") == 5
    for value in ("0", "-1", "abc", "1.5"):
        with pytest.raises(
            argparse.ArgumentTypeError, match="repeat must be a positive integer"
        ):
            _repeat_count(value)


def test_aggregate_success_rate_averages_and_failure_counts(tmp_path: Path):
    results = [
        result(
            "run-1",
            success=True,
            steps=2,
            calls=1,
            input_tokens=10,
            output_tokens=2,
            elapsed=1.0,
        ),
        result(
            "run-2",
            success=False,
            steps=4,
            calls=3,
            input_tokens=20,
            output_tokens=4,
            elapsed=3.0,
            failure_type="timeout",
        ),
        result(
            "run-3",
            success=False,
            steps=6,
            calls=5,
            input_tokens=30,
            output_tokens=6,
            elapsed=2.0,
        ),
    ]
    outcomes = [(item, tmp_path / f"{item.run_id}.json") for item in results]

    summary = aggregate_results("repeat-test", "created", outcomes)

    assert summary.total_runs == 3
    assert summary.successful_runs == 1
    assert summary.failed_runs == 2
    assert summary.success_rate == 0.333333
    assert summary.average_agent_steps == 4.0
    assert summary.average_tool_calls == 3.0
    assert summary.average_input_tokens == 20.0
    assert summary.average_output_tokens == 4.0
    assert summary.average_total_tokens == 24.0
    assert summary.average_elapsed_seconds == 2.0
    assert summary.min_elapsed_seconds == 1.0
    assert summary.max_elapsed_seconds == 3.0
    assert summary.failure_type_counts == {"timeout": 1, "unspecified": 1}
    assert [item.run_id for item in summary.individual_runs] == [
        "run-1",
        "run-2",
        "run-3",
    ]
    assert "average_tests_passed" not in summary.to_dict()
    assert "average_tests_failed" not in summary.to_dict()


def test_repeats_reset_workspace_preserve_results_and_recipe_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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

    summary, summary_path = run_repeated_benchmark(
        tmp_path,
        "task01_exact",
        MockModelAdapter(),
        repeat=3,
        recipe=recipe(),
        max_steps=8,
    )

    assert len(reset_contents) == 3
    assert all("return a * b" in content for content in reset_contents)
    assert summary.total_runs == summary.successful_runs == 3
    assert summary.failed_runs == 0
    assert summary.success_rate == 1.0
    assert summary.context_mode == "recipe"
    assert summary.recipe_id == "recipe_repeat"
    assert summary_path.exists()
    persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted_summary == summary.to_dict()

    assert len(summary.individual_runs) == 3
    for individual in summary.individual_runs:
        result_path = Path(individual.result_path)
        assert result_path.exists()
        persisted = json.loads(result_path.read_text(encoding="utf-8"))
        assert persisted["run_id"] == individual.run_id
        assert persisted["success"] is True
        assert persisted["context_mode"] == "recipe"
        assert persisted["recipe_id"] == "recipe_repeat"
