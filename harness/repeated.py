"""Aggregate metrics for repeated benchmark conditions."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from .metrics import RunResult


@dataclass(frozen=True)
class IndividualRunSummary:
    run_id: str
    success: bool
    failure_type: str | None
    result_path: str


@dataclass(frozen=True)
class RepeatedRunSummary:
    aggregate_id: str
    task_id: str
    model_provider: str
    model_name: str
    context_mode: str
    source_experience_id: str | None
    recipe_id: str | None
    source_recipe_id: str | None
    transfer_knowledge_id: str | None
    scout_handoff_id: str | None
    scout_model: str | None
    scout_input_tokens: int
    scout_output_tokens: int
    scout_total_tokens: int
    scout_elapsed_seconds: float
    source_scout_handoff_id: str | None
    compact_scout_id: str | None
    scout_accounting_mode: str | None
    max_steps: int
    created_at: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    average_agent_steps: float
    average_tool_calls: float
    average_input_tokens: float
    average_output_tokens: float
    average_total_tokens: float
    average_total_inference_tokens: float
    average_elapsed_seconds: float
    average_total_inference_elapsed_seconds: float
    frozen_experiment_total_inference_tokens: int
    frozen_experiment_total_inference_elapsed_seconds: float
    estimated_deployment_total_inference_tokens: int
    estimated_deployment_total_inference_elapsed_seconds: float
    min_elapsed_seconds: float
    max_elapsed_seconds: float
    failure_type_counts: dict[str, int]
    individual_runs: list[IndividualRunSummary]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def write_json(self, results_dir: Path) -> Path:
        results_dir.mkdir(parents=True, exist_ok=True)
        destination = results_dir / f"{self.aggregate_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def _average(values: Sequence[int | float]) -> float:
    return round(sum(values) / len(values), 6)


def aggregate_results(
    aggregate_id: str,
    created_at: str,
    outcomes: Sequence[tuple[RunResult, Path]],
) -> RepeatedRunSummary:
    if not outcomes:
        raise ValueError("at least one run is required for aggregation")
    results = [result for result, _ in outcomes]
    first = results[0]
    identity = (
        first.task_id,
        first.model_provider,
        first.model_name,
        first.context_mode,
        first.source_experience_id,
        first.recipe_id,
        first.source_recipe_id,
        first.transfer_knowledge_id,
        first.scout_handoff_id,
        first.scout_model,
        first.scout_input_tokens,
        first.scout_output_tokens,
        first.scout_total_tokens,
        first.scout_elapsed_seconds,
        first.source_scout_handoff_id,
        first.compact_scout_id,
        first.scout_accounting_mode,
        first.max_steps,
    )
    if any(
        (
            result.task_id,
            result.model_provider,
            result.model_name,
            result.context_mode,
            result.source_experience_id,
            result.recipe_id,
            result.source_recipe_id,
            result.transfer_knowledge_id,
            result.scout_handoff_id,
            result.scout_model,
            result.scout_input_tokens,
            result.scout_output_tokens,
            result.scout_total_tokens,
            result.scout_elapsed_seconds,
            result.source_scout_handoff_id,
            result.compact_scout_id,
            result.scout_accounting_mode,
            result.max_steps,
        )
        != identity
        for result in results[1:]
    ):
        raise ValueError("cannot aggregate different benchmark conditions")

    successful = sum(result.success for result in results)
    failures = Counter(
        result.failure_type or "unspecified"
        for result in results
        if not result.success
    )
    elapsed = [result.elapsed_seconds for result in results]
    return RepeatedRunSummary(
        aggregate_id=aggregate_id,
        task_id=first.task_id,
        model_provider=first.model_provider,
        model_name=first.model_name,
        context_mode=first.context_mode,
        source_experience_id=first.source_experience_id,
        recipe_id=first.recipe_id,
        source_recipe_id=first.source_recipe_id,
        transfer_knowledge_id=first.transfer_knowledge_id,
        scout_handoff_id=first.scout_handoff_id,
        scout_model=first.scout_model,
        scout_input_tokens=first.scout_input_tokens,
        scout_output_tokens=first.scout_output_tokens,
        scout_total_tokens=first.scout_total_tokens,
        scout_elapsed_seconds=first.scout_elapsed_seconds,
        source_scout_handoff_id=first.source_scout_handoff_id,
        compact_scout_id=first.compact_scout_id,
        scout_accounting_mode=first.scout_accounting_mode,
        max_steps=first.max_steps,
        created_at=created_at,
        total_runs=len(results),
        successful_runs=successful,
        failed_runs=len(results) - successful,
        success_rate=round(successful / len(results), 6),
        average_agent_steps=_average([result.agent_steps for result in results]),
        average_tool_calls=_average([result.tool_calls for result in results]),
        average_input_tokens=_average([result.input_tokens for result in results]),
        average_output_tokens=_average([result.output_tokens for result in results]),
        average_total_tokens=_average([result.total_tokens for result in results]),
        average_total_inference_tokens=_average(
            [result.total_inference_tokens() for result in results]
        ),
        average_elapsed_seconds=_average(elapsed),
        average_total_inference_elapsed_seconds=round(
            _average(elapsed) + first.scout_elapsed_seconds, 6
        ),
        frozen_experiment_total_inference_tokens=(
            sum(result.total_tokens for result in results)
            + first.scout_total_tokens
        ),
        frozen_experiment_total_inference_elapsed_seconds=round(
            sum(result.elapsed_seconds for result in results)
            + first.scout_elapsed_seconds,
            6,
        ),
        estimated_deployment_total_inference_tokens=sum(
            result.total_inference_tokens() for result in results
        ),
        estimated_deployment_total_inference_elapsed_seconds=round(
            sum(result.total_inference_elapsed_seconds() for result in results),
            6,
        ),
        min_elapsed_seconds=min(elapsed),
        max_elapsed_seconds=max(elapsed),
        failure_type_counts=dict(sorted(failures.items())),
        individual_runs=[
            IndividualRunSummary(
                result.run_id,
                result.success,
                result.failure_type,
                str(path),
            )
            for result, path in outcomes
        ],
    )
