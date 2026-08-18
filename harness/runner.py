"""CLI and orchestration for benchmark runs."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from experience.capture import capture_experience
from experience.schema import ExperienceRecord, load_experience
from recipe.compiler import compile_recipe
from recipe.schema import ExperienceRecipe, load_recipe
from transfer.compiler import compile_transfer_knowledge
from transfer.schema import TransferKnowledge, load_transfer_knowledge

from .agent import AgentRun, CodingAgent
from .metrics import RunResult
from .models import AgentContext, MockModelAdapter, ModelAdapter, ModelPricing
from .ollama_adapter import (
    OllamaDiagnosticResult,
    OllamaModelAdapter,
    OllamaProviderError,
)
from .openai_adapter import OpenAIModelAdapter
from .prompting import build_model_prompt
from .repeated import RepeatedRunSummary, aggregate_results
from .tools import WorkspaceTools, reset_workspace
from .trajectory import build_trajectory, trajectory_diagnostics
from .transformers_adapter import (
    TransformersModelAdapter,
    TransformersProviderError,
)
from .vertex_adapter import VertexGeminiAdapter


def load_task(repo_root: Path, task_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
        raise ValueError("task id contains forbidden characters")
    task_dir = repo_root / "tasks" / task_id
    metadata_path = task_dir / "task.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load task {task_id!r}: {exc}") from exc
    required = {"task_id", "description", "test_command"}
    if not isinstance(metadata, dict) or not required.issubset(metadata):
        raise ValueError(f"task {task_id!r} has invalid metadata")
    if metadata["task_id"] != task_id:
        raise ValueError("task id does not match its directory")
    if not (task_dir / "workspace").is_dir():
        raise ValueError("task workspace is missing")
    return metadata


def _test_counts(output: str, returncode: int) -> tuple[int, int]:
    passed = sum(int(value) for value in re.findall(r"(\d+) passed", output))
    failed = sum(int(value) for value in re.findall(r"(\d+) failed", output))
    if returncode != 0 and failed == 0:
        failed = 1
    return passed, failed


def run_benchmark(
    repo_root: Path,
    task_id: str,
    model: ModelAdapter,
    *,
    run_id: str | None = None,
    experience: ExperienceRecord | None = None,
    recipe: ExperienceRecipe | None = None,
    transfer_knowledge: TransferKnowledge | None = None,
    max_steps: int = 20,
) -> tuple[RunResult, Path]:
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    if sum(
        context is not None
        for context in (experience, recipe, transfer_knowledge)
    ) > 1:
        raise ValueError("benchmark contexts are mutually exclusive")
    repo_root = repo_root.resolve()
    prior_experience = experience
    prior_recipe = recipe
    prior_transfer = transfer_knowledge
    if prior_recipe is not None and prior_recipe.task_id != task_id:
        raise ValueError("recipe task_id does not match the benchmark task")
    context_mode = (
        "raw_experience"
        if prior_experience is not None
        else "recipe"
        if prior_recipe is not None
        else "transfer_knowledge"
        if prior_transfer is not None
        else "none"
    )
    source_experience_id = (
        prior_experience.experience_id
        if prior_experience is not None
        else prior_recipe.source_experience_id if prior_recipe is not None else None
    )
    task = load_task(repo_root, task_id)
    run_id = run_id or f"{task_id}-{uuid.uuid4().hex[:12]}"
    workspace = reset_workspace(
        repo_root / "tasks" / task_id / "workspace",
        repo_root / ".workspaces" / task_id,
    )
    tools = WorkspaceTools(workspace, task["test_command"])
    start_wall = datetime.now(timezone.utc)
    start_clock = perf_counter()
    provider_failure: OllamaProviderError | TransformersProviderError | None = None
    try:
        agent_run = CodingAgent(model, tools, max_steps=max_steps).run(
            task_id,
            task["description"],
            prior_experience=(
                prior_experience.to_dict()
                if prior_experience
                else prior_recipe.to_dict()
                if prior_recipe
                else prior_transfer.to_dict()
                if prior_transfer
                else None
            ),
        )
    except (OllamaProviderError, TransformersProviderError) as exc:
        provider_failure = exc
        agent_run = AgentRun(
            steps=0,
            tool_calls=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
            history=(),
            finished=False,
            max_steps_exhausted=False,
        )
    verification = tools.run_tests()
    elapsed = perf_counter() - start_clock
    end_wall = datetime.now(timezone.utc)
    combined_output = verification.stdout + "\n" + verification.stderr
    passed, failed = _test_counts(combined_output, verification.returncode)
    successful = provider_failure is None and verification.returncode == 0
    trajectory = build_trajectory(agent_run.history)
    diagnostics = trajectory_diagnostics(trajectory)
    failure_type = provider_failure.failure_type if provider_failure else None
    failure_message = str(provider_failure) if provider_failure else None
    if (
        not successful
        and provider_failure is None
        and agent_run.max_steps_exhausted
    ):
        failure_type = "max_steps_exhausted"
        failure_message = (
            f"Agent did not complete the task within {max_steps} steps."
        )
    captured_experience = capture_experience(
        pristine_workspace=repo_root / "tasks" / task_id / "workspace",
        active_workspace=workspace,
        task_id=task_id,
        producer_model=model.name,
        problem=task["description"],
        environment=task.get("environment", {}),
        verification_command=task["test_command"],
        passed=passed,
        failed=failed,
        successful=successful,
        experiences_dir=repo_root / "experiences",
        created_at=end_wall.isoformat(),
        started_at=start_wall.isoformat(),
        completed_at=end_wall.isoformat(),
    )
    experience_record, experience_path = (
        captured_experience if captured_experience else (None, None)
    )
    result = RunResult(
        run_id=run_id,
        task_id=task_id,
        model_provider=model.provider,
        model_name=model.name,
        experience_used=context_mode != "none",
        experience_id=(
            source_experience_id
        ),
        success=successful,
        start_time=start_wall.isoformat(),
        end_time=end_wall.isoformat(),
        elapsed_seconds=round(elapsed, 6),
        agent_steps=agent_run.steps,
        tool_calls=agent_run.tool_calls,
        test_command=task["test_command"],
        tests_passed=passed,
        tests_failed=failed,
        input_tokens=agent_run.input_tokens,
        output_tokens=agent_run.output_tokens,
        total_tokens=agent_run.total_tokens,
        estimated_cost_usd=(
            round(agent_run.estimated_cost_usd, 8)
            if agent_run.estimated_cost_usd is not None
            else None
        ),
        max_steps=max_steps,
        trajectory=trajectory,
        trajectory_diagnostics=diagnostics,
        failure_type=failure_type,
        failure_message=failure_message,
        generated_experience_id=(
            experience_record.experience_id if experience_record else None
        ),
        generated_experience_path=(
            str(experience_path) if experience_path else None
        ),
        context_mode=context_mode,
        source_experience_id=source_experience_id,
        recipe_id=prior_recipe.recipe_id if prior_recipe else None,
        source_recipe_id=(
            prior_transfer.source_recipe_id if prior_transfer else None
        ),
        transfer_knowledge_id=(
            prior_transfer.transfer_knowledge_id if prior_transfer else None
        ),
    )
    result_path = result.write_json(repo_root / "results")
    return result, result_path


def run_comparison(
    repo_root: Path,
    task_id: str,
    model: ModelAdapter,
    experience: ExperienceRecord,
    *,
    max_steps: int = 20,
) -> tuple[RunResult, RunResult]:
    """Run no-experience and with-experience smoke tests from fresh workspaces."""

    baseline, _ = run_benchmark(
        repo_root, task_id, model, experience=None, max_steps=max_steps
    )
    experiment, _ = run_benchmark(
        repo_root,
        task_id,
        model,
        experience=experience,
        max_steps=max_steps,
    )
    return baseline, experiment


def run_representation_comparison(
    repo_root: Path,
    task_id: str,
    model: ModelAdapter,
    experience: ExperienceRecord,
    recipe: ExperienceRecipe,
    *,
    max_steps: int = 20,
) -> tuple[RunResult, RunResult, RunResult]:
    """Run none, raw-experience, and recipe conditions from clean workspaces."""

    if experience.task_id != task_id or recipe.task_id != task_id:
        raise ValueError("comparison contexts do not match the benchmark task")
    if recipe.source_experience_id != experience.experience_id:
        raise ValueError("recipe source does not match the selected experience")
    baseline, _ = run_benchmark(
        repo_root, task_id, model, max_steps=max_steps
    )
    raw, _ = run_benchmark(
        repo_root,
        task_id,
        model,
        experience=experience,
        max_steps=max_steps,
    )
    compact, _ = run_benchmark(
        repo_root,
        task_id,
        model,
        recipe=recipe,
        max_steps=max_steps,
    )
    return baseline, raw, compact


def run_repeated_benchmark(
    repo_root: Path,
    task_id: str,
    model: ModelAdapter,
    *,
    repeat: int,
    experience: ExperienceRecord | None = None,
    recipe: ExperienceRecipe | None = None,
    transfer_knowledge: TransferKnowledge | None = None,
    max_steps: int = 20,
) -> tuple[RepeatedRunSummary, Path]:
    """Repeat one unchanged benchmark condition from pristine workspaces."""

    if repeat < 1:
        raise ValueError("repeat must be positive")
    aggregate_id = f"repeat_{task_id}_{uuid.uuid4().hex[:12]}"
    outcomes: list[tuple[RunResult, Path]] = []
    for index in range(1, repeat + 1):
        outcomes.append(
            run_benchmark(
                repo_root,
                task_id,
                model,
                run_id=f"{aggregate_id}-run-{index:02d}",
                experience=experience,
                recipe=recipe,
                transfer_knowledge=transfer_knowledge,
                max_steps=max_steps,
            )
        )
    summary = aggregate_results(
        aggregate_id,
        datetime.now(timezone.utc).isoformat(),
        outcomes,
    )
    summary_path = summary.write_json(repo_root.resolve() / "results")
    return summary, summary_path


def _model_from_name(
    name: str,
    pricing: ModelPricing | None = None,
    provider: str | None = None,
) -> ModelAdapter:
    selected_provider = provider or ("mock" if name == "mock" else "openai")
    if selected_provider == "mock":
        if name != "mock":
            raise ValueError("the mock provider requires --model mock")
        return MockModelAdapter()
    if name == "mock":
        raise ValueError(f"--model is required for provider {selected_provider}")
    if selected_provider == "openai":
        return OpenAIModelAdapter(name, pricing=pricing)
    if selected_provider == "vertex":
        return VertexGeminiAdapter(name, pricing=pricing)
    if selected_provider == "ollama":
        return OllamaModelAdapter(name)
    if selected_provider == "transformers":
        return TransformersModelAdapter(name)
    raise ValueError(f"unsupported model provider: {selected_provider}")


def _display_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "unsupported"
    return str(value)


def print_comparison(baseline: RunResult, experiment: RunResult) -> None:
    rows = (
        ("Success", baseline.success, experiment.success),
        ("Agent steps", baseline.agent_steps, experiment.agent_steps),
        ("Tool calls", baseline.tool_calls, experiment.tool_calls),
        ("Max steps", baseline.max_steps, experiment.max_steps),
        ("Input tokens", baseline.input_tokens, experiment.input_tokens),
        ("Output tokens", baseline.output_tokens, experiment.output_tokens),
        ("Total tokens", baseline.total_tokens, experiment.total_tokens),
        ("Elapsed seconds", baseline.elapsed_seconds, experiment.elapsed_seconds),
        (
            "Estimated cost USD",
            baseline.estimated_cost_usd,
            experiment.estimated_cost_usd,
        ),
        ("Tests passed", baseline.tests_passed, experiment.tests_passed),
        ("Tests failed", baseline.tests_failed, experiment.tests_failed),
        ("Failure type", baseline.failure_type, experiment.failure_type),
        ("Failure message", baseline.failure_message, experiment.failure_message),
    )
    print("Smoke-test comparison only; no statistical improvement is claimed.")
    print(f"{'Metric':<22}{'No Experience':<20}{'With Experience':<20}")
    print("-" * 62)
    for metric, without, with_experience in rows:
        print(
            f"{metric:<22}{_display_value(without):<20}"
            f"{_display_value(with_experience):<20}"
        )


def print_representation_comparison(
    baseline: RunResult, raw: RunResult, compact: RunResult
) -> None:
    rows = (
        ("Success", baseline.success, raw.success, compact.success),
        ("Agent steps", baseline.agent_steps, raw.agent_steps, compact.agent_steps),
        ("Tool calls", baseline.tool_calls, raw.tool_calls, compact.tool_calls),
        ("Max steps", baseline.max_steps, raw.max_steps, compact.max_steps),
        ("Input tokens", baseline.input_tokens, raw.input_tokens, compact.input_tokens),
        (
            "Output tokens",
            baseline.output_tokens,
            raw.output_tokens,
            compact.output_tokens,
        ),
        ("Total tokens", baseline.total_tokens, raw.total_tokens, compact.total_tokens),
        (
            "Elapsed seconds",
            baseline.elapsed_seconds,
            raw.elapsed_seconds,
            compact.elapsed_seconds,
        ),
        ("Tests passed", baseline.tests_passed, raw.tests_passed, compact.tests_passed),
        ("Tests failed", baseline.tests_failed, raw.tests_failed, compact.tests_failed),
        ("Failure type", baseline.failure_type, raw.failure_type, compact.failure_type),
    )
    print("Three-condition smoke test; no statistical improvement is claimed.")
    print(
        f"{'Metric':<22}{'No Experience':<20}"
        f"{'Raw Experience':<20}{'Recipe':<20}"
    )
    print("-" * 82)
    for metric, without, raw_value, recipe_value in rows:
        print(
            f"{metric:<22}{_display_value(without):<20}"
            f"{_display_value(raw_value):<20}"
            f"{_display_value(recipe_value):<20}"
        )


def print_trajectory(title: str, result: RunResult) -> None:
    print(f"\n{title}\n")
    if not result.trajectory:
        print("(no executed actions)")
    for entry in result.trajectory:
        target = str(entry["target"] or "")
        print(
            f"{int(entry['step']):02d}  {str(entry['action']):<18}"
            f"{target:<34}{entry['outcome']}"
        )
    print(
        "diagnostics="
        + json.dumps(result.trajectory_diagnostics, sort_keys=True)
    )


def print_repeated_summary(summary: RepeatedRunSummary) -> None:
    print("\nINDIVIDUAL RUNS\n")
    for index, run in enumerate(summary.individual_runs, start=1):
        status = "PASS" if run.success else "FAIL"
        failure = f" failure_type={run.failure_type}" if not run.success else ""
        print(f"{index:02d}  {run.run_id}  {status}{failure}")
    rows = (
        ("Total runs", summary.total_runs),
        ("Successful runs", summary.successful_runs),
        ("Failed runs", summary.failed_runs),
        ("Success rate", summary.success_rate),
        ("Average agent steps", summary.average_agent_steps),
        ("Average tool calls", summary.average_tool_calls),
        ("Average input tokens", summary.average_input_tokens),
        ("Average output tokens", summary.average_output_tokens),
        ("Average total tokens", summary.average_total_tokens),
        ("Average elapsed seconds", summary.average_elapsed_seconds),
        ("Min elapsed seconds", summary.min_elapsed_seconds),
        ("Max elapsed seconds", summary.max_elapsed_seconds),
        (
            "Failure-type counts",
            json.dumps(summary.failure_type_counts, sort_keys=True),
        ),
    )
    print("\nAGGREGATE SUMMARY\n")
    for label, value in rows:
        print(f"{label:<26}{value}")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _repeat_count(value: str) -> int:
    try:
        return _positive_int(value)
    except argparse.ArgumentTypeError as exc:
        raise argparse.ArgumentTypeError(
            "repeat must be a positive integer"
        ) from exc


def run_ollama_diagnostics(
    repo_root: Path,
    task_id: str,
    adapter: OllamaModelAdapter,
) -> list[tuple[str, OllamaDiagnosticResult]]:
    """Run three non-mutating requests that isolate Ollama request complexity."""

    task = load_task(repo_root.resolve(), task_id)
    first_turn_context = AgentContext(
        task_id=task_id,
        task_description=task["description"],
        available_tools=WorkspaceTools.ACTIONS,
        history=(),
        prior_experience=None,
        current_step=1,
        max_steps=20,
    )
    cases = (
        (
            "A - trivial",
            "Reply with only OK",
            False,
            False,
        ),
        (
            "B - structured action",
            "Return one valid structured coding-agent action.",
            True,
            False,
        ),
        (
            "C - Task 02 first turn",
            build_model_prompt(first_turn_context),
            True,
            True,
        ),
    )
    results = []
    for label, prompt, structured, agent_style in cases:
        result = adapter.diagnose_request(
            prompt,
            structured_schema=structured,
            agent_style=agent_style,
        )
        results.append((label, result))
        print(label)
        print(f"  success: {str(result.success).lower()}")
        print(f"  elapsed_seconds: {result.elapsed_seconds}")
        print(f"  input_tokens: {result.input_tokens}")
        print(f"  output_tokens: {result.output_tokens}")
        print(f"  request_body_bytes: {result.request_body_bytes}")
        print(f"  structured_schema: {str(result.structured_schema).lower()}")
        if not result.success:
            print(f"  failure_type: {result.failure_type}")
            print(f"  failure_message: {result.failure_message}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task")
    parser.add_argument(
        "--provider",
        choices=("mock", "openai", "vertex", "ollama", "transformers"),
    )
    parser.add_argument("--model", default="mock")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    experience_group = parser.add_mutually_exclusive_group()
    experience_group.add_argument("--experience", type=Path)
    experience_group.add_argument("--compare-experience", type=Path)
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--transfer-knowledge", type=Path)
    parser.add_argument("--compare-representations", action="store_true")
    parser.add_argument("--compile-recipe", type=Path)
    parser.add_argument("--compile-transfer-knowledge", type=Path)
    parser.add_argument("--input-cost-per-million", type=float)
    parser.add_argument("--output-cost-per-million", type=float)
    parser.add_argument("--diagnose-ollama", action="store_true")
    parser.add_argument("--max-steps", type=_positive_int, default=20)
    parser.add_argument("--repeat", type=_repeat_count, default=1)
    args = parser.parse_args()
    if (
        not args.diagnose_ollama
        and not args.compile_recipe
        and not args.compile_transfer_knowledge
        and not args.task
    ):
        parser.error("--task is required")
    if args.diagnose_ollama and args.provider != "ollama":
        parser.error("--diagnose-ollama requires --provider ollama")
    if (args.input_cost_per_million is None) != (
        args.output_cost_per_million is None
    ):
        parser.error("both pricing arguments must be supplied together")
    if args.repeat != 1 and (
        args.compile_recipe
        or args.compile_transfer_knowledge
        or args.diagnose_ollama
        or args.compare_experience
        or args.compare_representations
    ):
        parser.error("--repeat cannot be combined with compile or comparison modes")
    if args.compile_recipe:
        source_path = args.compile_recipe
        if not source_path.is_absolute():
            source_path = args.root / source_path
        try:
            source_experience = load_experience(source_path)
            compiled = compile_recipe(source_experience)
        except ValueError as exc:
            parser.error(str(exc))
        recipe_path = compiled.write_json(args.root / "recipes")
        print(f"recipe={recipe_path}")
        print(json.dumps(compiled.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.compile_transfer_knowledge:
        source_path = args.compile_transfer_knowledge
        if not source_path.is_absolute():
            source_path = args.root / source_path
        try:
            source_recipe = load_recipe(source_path)
            compiled_transfer = compile_transfer_knowledge(source_recipe)
        except ValueError as exc:
            parser.error(str(exc))
        transfer_path = compiled_transfer.write_json(
            args.root / "transfer_knowledge"
        )
        print(f"transfer_knowledge={transfer_path}")
        print(
            json.dumps(
                compiled_transfer.to_dict(), indent=2, sort_keys=True
            )
        )
        return 0
    if args.compare_representations:
        if args.experience is None or args.recipe is None:
            parser.error(
                "--compare-representations requires --experience and --recipe"
            )
        if args.compare_experience is not None:
            parser.error(
                "--compare-representations cannot use --compare-experience"
            )
        if args.transfer_knowledge is not None:
            parser.error(
                "--compare-representations cannot use --transfer-knowledge"
            )
    elif sum(
        context is not None
        for context in (args.experience, args.recipe, args.transfer_knowledge)
    ) > 1:
        parser.error("benchmark context options are mutually exclusive")
    if args.compare_experience is not None and (
        args.recipe is not None or args.transfer_knowledge is not None
    ):
        parser.error(
            "--compare-experience cannot be combined with another context"
        )
    pricing = None
    if args.input_cost_per_million is not None:
        pricing = ModelPricing(
            args.input_cost_per_million, args.output_cost_per_million
        )
    try:
        model = _model_from_name(args.model, pricing, args.provider)
    except ValueError as exc:
        parser.error(str(exc))
    if args.diagnose_ollama:
        assert isinstance(model, OllamaModelAdapter)
        diagnostic_task = args.task or "task02_config_path"
        results = run_ollama_diagnostics(args.root, diagnostic_task, model)
        return 0 if all(result.success for _, result in results) else 1
    selected_path = args.experience or args.compare_experience
    experience = None
    if selected_path:
        if not selected_path.is_absolute():
            selected_path = args.root / selected_path
        try:
            experience = load_experience(selected_path)
        except ValueError as exc:
            parser.error(str(exc))
    recipe = None
    if args.recipe:
        recipe_path = args.recipe
        if not recipe_path.is_absolute():
            recipe_path = args.root / recipe_path
        try:
            recipe = load_recipe(recipe_path)
        except ValueError as exc:
            parser.error(str(exc))
    transfer_knowledge = None
    if args.transfer_knowledge:
        transfer_path = args.transfer_knowledge
        if not transfer_path.is_absolute():
            transfer_path = args.root / transfer_path
        try:
            transfer_knowledge = load_transfer_knowledge(transfer_path)
        except ValueError as exc:
            parser.error(str(exc))
    if args.compare_representations:
        assert experience is not None and recipe is not None
        try:
            baseline, raw, compact = run_representation_comparison(
                args.root,
                args.task,
                model,
                experience,
                recipe,
                max_steps=args.max_steps,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print_representation_comparison(baseline, raw, compact)
        print_trajectory("NO EXPERIENCE TRAJECTORY", baseline)
        print_trajectory("RAW EXPERIENCE TRAJECTORY", raw)
        print_trajectory("RECIPE TRAJECTORY", compact)
        return 0 if baseline.success and raw.success and compact.success else 1
    if args.repeat > 1:
        summary, summary_path = run_repeated_benchmark(
            args.root,
            args.task,
            model,
            repeat=args.repeat,
            experience=experience,
            recipe=recipe,
            transfer_knowledge=transfer_knowledge,
            max_steps=args.max_steps,
        )
        print_repeated_summary(summary)
        print(f"aggregate={summary_path}")
        return 0 if summary.successful_runs == summary.total_runs else 1
    if args.compare_experience:
        assert experience is not None
        baseline, experiment = run_comparison(
            args.root,
            args.task,
            model,
            experience,
            max_steps=args.max_steps,
        )
        print_comparison(baseline, experiment)
        print_trajectory("NO EXPERIENCE TRAJECTORY", baseline)
        print_trajectory("WITH EXPERIENCE TRAJECTORY", experiment)
        return 0 if baseline.success and experiment.success else 1
    result, result_path = run_benchmark(
        args.root,
        args.task,
        model,
        experience=experience,
        recipe=recipe,
        transfer_knowledge=transfer_knowledge,
        max_steps=args.max_steps,
    )
    status = "PASS" if result.success else "FAIL"
    print(
        f"{status} task={result.task_id} model={result.model_name} "
        f"steps={result.agent_steps} tools={result.tool_calls} "
        f"tests={result.tests_passed} passed/{result.tests_failed} failed"
    )
    print(f"result={result_path}")
    if result.generated_experience_path:
        print(f"generated_experience={result.generated_experience_path}")
    print_trajectory("TRAJECTORY", result)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
