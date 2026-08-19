"""Read-only behavioral measurements from completed result JSON artifacts."""

from __future__ import annotations

import argparse
import glob
import json
import re
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Sequence


_TEST_FAILURE = re.compile(r"(\d+)\s+failed")
_INVALID_TOOL_MARKERS = (
    "invalid fields for",
    "unsafe command argument",
    "command is not allowlisted",
    "absolute paths are forbidden",
    "path escapes the active workspace",
    "unknown action",
    "action must be an object",
    "command must be a non-empty list",
    "path must be a non-empty string",
    "content must be a string",
)


@dataclass(frozen=True)
class AnalysisContract:
    """Optional task semantics declared before benchmark execution."""

    relevant_source_files: frozenset[str] | None = None
    allowed_output_files: frozenset[str] | None = None
    pristine_tests_passed: int | None = None
    pristine_tests_failed: int | None = None

    @classmethod
    def from_dict(cls, value: object) -> "AnalysisContract":
        if not isinstance(value, dict):
            raise ValueError("analysis_contract must be a JSON object")

        def paths(name: str) -> frozenset[str] | None:
            raw = value.get(name)
            if raw is None:
                return None
            if not isinstance(raw, list) or not all(
                isinstance(path, str) and path.strip() for path in raw
            ):
                raise ValueError(f"analysis_contract.{name} must be string paths")
            return frozenset(raw)

        def count(name: str) -> int | None:
            raw = value.get(name)
            if raw is None:
                return None
            if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
                raise ValueError(
                    f"analysis_contract.{name} must be a non-negative integer"
                )
            return raw

        return cls(
            relevant_source_files=paths("relevant_source_files"),
            allowed_output_files=paths("allowed_output_files"),
            pristine_tests_passed=count("pristine_tests_passed"),
            pristine_tests_failed=count("pristine_tests_failed"),
        )


@dataclass(frozen=True)
class TrajectoryMetrics:
    run_id: str
    task_id: str
    final_success: bool
    final_tests_passed: int
    final_tests_failed: int
    test_execution_count: int
    file_read_count: int
    file_write_count: int
    unique_files_read: list[str]
    unique_files_written: list[str]
    repeated_identical_actions: int
    max_repeated_action_count: int
    malformed_model_output_count: int
    invalid_tool_action_count: int
    verification_used: bool
    revision_after_test_failure: bool
    verification_after_revision: bool
    max_steps_exhausted: bool
    agent_steps: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_seconds: float
    analysis_contract_applied: bool
    relevant_source_read: bool | None = None
    relevant_source_write: bool | None = None
    unexpected_file_created_or_written: bool | None = None
    passing_test_regression_count: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_analysis_contract(path: Path) -> AnalysisContract:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"analysis metadata does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load analysis metadata {path}: {exc}") from exc
    if isinstance(data, dict) and "analysis_contract" in data:
        data = data["analysis_contract"]
    return AnalysisContract.from_dict(data)


def _non_negative_int(result: dict[str, Any], name: str) -> int:
    value = result.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"result has invalid {name}")
    return value


def _successful(entry: dict[str, Any]) -> bool:
    outcome = entry.get("outcome")
    return isinstance(outcome, str) and outcome.startswith("success")


def _test_failed(entry: dict[str, Any]) -> bool:
    if entry.get("action") != "run_tests":
        return False
    outcome = entry.get("outcome")
    if not isinstance(outcome, str):
        return False
    return any(int(count) > 0 for count in _TEST_FAILURE.findall(outcome))


def _invalid_tool_action(entry: dict[str, Any]) -> bool:
    action = entry.get("action")
    outcome = entry.get("outcome")
    if action == "invalid_action":
        return True
    if not isinstance(outcome, str) or not outcome.startswith("error:"):
        return False
    lowered = outcome.lower()
    return any(marker in lowered for marker in _INVALID_TOOL_MARKERS)


def analyze_result(
    result: dict[str, Any],
    analysis_contract: AnalysisContract | None = None,
) -> TrajectoryMetrics:
    """Measure one completed run without modifying or semantically interpreting it."""

    if not isinstance(result, dict):
        raise ValueError("result must be a JSON object")
    run_id = result.get("run_id")
    task_id = result.get("task_id")
    if not isinstance(run_id, str) or not isinstance(task_id, str):
        raise ValueError("result has missing run_id or task_id")
    success = result.get("success")
    if not isinstance(success, bool):
        raise ValueError("result has invalid success")
    trajectory = result.get("trajectory")
    if not isinstance(trajectory, list) or not all(
        isinstance(entry, dict) for entry in trajectory
    ):
        raise ValueError("result has invalid trajectory")

    action_counts = Counter(
        (str(entry.get("action")), entry.get("target")) for entry in trajectory
    )
    computed_repeated = sum(
        count - 1 for count in action_counts.values() if count > 1
    )
    diagnostics = result.get("trajectory_diagnostics")
    diagnostic_repeated = (
        diagnostics.get("repeated_identical_actions")
        if isinstance(diagnostics, dict)
        else None
    )
    repeated = (
        diagnostic_repeated
        if isinstance(diagnostic_repeated, int)
        and not isinstance(diagnostic_repeated, bool)
        and diagnostic_repeated >= 0
        else computed_repeated
    )

    successful_reads = [
        entry
        for entry in trajectory
        if entry.get("action") == "read_file" and _successful(entry)
    ]
    successful_writes = [
        entry
        for entry in trajectory
        if entry.get("action") == "write_file" and _successful(entry)
    ]
    read_targets = sorted(
        {
            target
            for entry in successful_reads
            if isinstance((target := entry.get("target")), str)
        }
    )
    write_targets = sorted(
        {
            target
            for entry in successful_writes
            if isinstance((target := entry.get("target")), str)
        }
    )
    failing_test_steps = [
        index for index, entry in enumerate(trajectory) if _test_failed(entry)
    ]
    revision_steps = [
        index
        for index, entry in enumerate(trajectory)
        if entry.get("action") == "write_file"
        and _successful(entry)
        and any(failure < index for failure in failing_test_steps)
    ]
    verification_after_revision = any(
        entry.get("action") == "run_tests"
        and any(revision < index for revision in revision_steps)
        for index, entry in enumerate(trajectory)
    )
    malformed_count = sum(
        entry.get("action") == "model_output_error"
        or (
            isinstance(entry.get("outcome"), str)
            and "malformed model output" in entry["outcome"].lower()
        )
        for entry in trajectory
    )
    elapsed = result.get("elapsed_seconds")
    if (
        not isinstance(elapsed, (int, float))
        or isinstance(elapsed, bool)
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        raise ValueError("result has invalid elapsed_seconds")

    contract_applied = analysis_contract is not None
    relevant_read = relevant_write = unexpected_write = None
    regression = None
    if analysis_contract is not None:
        if analysis_contract.relevant_source_files is not None:
            relevant_read = bool(
                set(read_targets) & analysis_contract.relevant_source_files
            )
            relevant_write = bool(
                set(write_targets) & analysis_contract.relevant_source_files
            )
        if analysis_contract.allowed_output_files is not None:
            unexpected_write = any(
                target not in analysis_contract.allowed_output_files
                for target in write_targets
            )
        if analysis_contract.pristine_tests_passed is not None:
            regression = max(
                0,
                analysis_contract.pristine_tests_passed
                - _non_negative_int(result, "tests_passed"),
            )

    return TrajectoryMetrics(
        run_id=run_id,
        task_id=task_id,
        final_success=success,
        final_tests_passed=_non_negative_int(result, "tests_passed"),
        final_tests_failed=_non_negative_int(result, "tests_failed"),
        test_execution_count=sum(
            entry.get("action") == "run_tests" for entry in trajectory
        ),
        file_read_count=len(successful_reads),
        file_write_count=len(successful_writes),
        unique_files_read=read_targets,
        unique_files_written=write_targets,
        repeated_identical_actions=repeated,
        max_repeated_action_count=max(action_counts.values(), default=0),
        malformed_model_output_count=malformed_count,
        invalid_tool_action_count=sum(
            _invalid_tool_action(entry) for entry in trajectory
        ),
        verification_used=any(
            entry.get("action") == "run_tests" for entry in trajectory
        ),
        revision_after_test_failure=bool(revision_steps),
        verification_after_revision=verification_after_revision,
        max_steps_exhausted=(result.get("failure_type") == "max_steps_exhausted"),
        agent_steps=_non_negative_int(result, "agent_steps"),
        tool_calls=_non_negative_int(result, "tool_calls"),
        input_tokens=_non_negative_int(result, "input_tokens"),
        output_tokens=_non_negative_int(result, "output_tokens"),
        total_tokens=_non_negative_int(result, "total_tokens"),
        elapsed_seconds=float(elapsed),
        analysis_contract_applied=contract_applied,
        relevant_source_read=relevant_read,
        relevant_source_write=relevant_write,
        unexpected_file_created_or_written=unexpected_write,
        passing_test_regression_count=regression,
    )


def analyze_result_file(
    path: Path,
    analysis_contract: AnalysisContract | None = None,
) -> TrajectoryMetrics:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"result does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load result {path}: {exc}") from exc
    return analyze_result(result, analysis_contract)


def _rate(values: Iterable[bool]) -> float:
    items = list(values)
    return round(sum(items) / len(items), 6)


def _mean(values: Iterable[int | float]) -> float:
    return round(mean(values), 6)


def _median(values: Iterable[int | float]) -> float:
    return round(float(median(values)), 6)


def aggregate_metrics(metrics: Sequence[TrajectoryMetrics]) -> dict[str, object]:
    """Aggregate raw, interpretable measures for one experimental condition."""

    if not metrics:
        raise ValueError("at least one run is required for aggregation")
    aggregate: dict[str, object] = {
        "number_of_runs": len(metrics),
        "success_rate": _rate(item.final_success for item in metrics),
        "mean_final_tests_passed": _mean(
            item.final_tests_passed for item in metrics
        ),
        "median_final_tests_passed": _median(
            item.final_tests_passed for item in metrics
        ),
        "mean_final_tests_failed": _mean(
            item.final_tests_failed for item in metrics
        ),
        "median_final_tests_failed": _median(
            item.final_tests_failed for item in metrics
        ),
        "verification_use_rate": _rate(item.verification_used for item in metrics),
        "revision_after_failure_rate": _rate(
            item.revision_after_test_failure for item in metrics
        ),
        "verification_after_revision_rate": _rate(
            item.verification_after_revision for item in metrics
        ),
        "malformed_output_rate": _rate(
            item.malformed_model_output_count > 0 for item in metrics
        ),
        "invalid_tool_action_rate": _rate(
            item.invalid_tool_action_count > 0 for item in metrics
        ),
        "max_step_exhaustion_rate": _rate(
            item.max_steps_exhausted for item in metrics
        ),
        "mean_repeated_identical_actions": _mean(
            item.repeated_identical_actions for item in metrics
        ),
        "mean_agent_steps": _mean(item.agent_steps for item in metrics),
        "mean_tool_calls": _mean(item.tool_calls for item in metrics),
        "mean_input_tokens": _mean(item.input_tokens for item in metrics),
        "mean_output_tokens": _mean(item.output_tokens for item in metrics),
        "mean_total_tokens": _mean(item.total_tokens for item in metrics),
        "mean_elapsed_seconds": _mean(item.elapsed_seconds for item in metrics),
    }
    optional_rates = {
        "relevant_source_read_rate": "relevant_source_read",
        "relevant_source_write_rate": "relevant_source_write",
        "unexpected_file_created_or_written_rate": (
            "unexpected_file_created_or_written"
        ),
    }
    for output_name, attribute in optional_rates.items():
        values = [getattr(item, attribute) for item in metrics]
        if all(value is not None for value in values):
            aggregate[output_name] = _rate(bool(value) for value in values)
    regressions = [item.passing_test_regression_count for item in metrics]
    if all(value is not None for value in regressions):
        numeric = [int(value) for value in regressions if value is not None]
        aggregate["mean_passing_test_regression_count"] = _mean(numeric)
        aggregate["median_passing_test_regression_count"] = _median(numeric)
    return aggregate


def _expanded_paths(positional: Sequence[Path], patterns: Sequence[str]) -> list[Path]:
    paths = [*positional]
    for pattern in patterns:
        for match in sorted(glob.glob(pattern)):
            path = Path(match)
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                paths.append(path)
                continue
            # Repeat globs commonly match both per-run files and their aggregate.
            # Aggregates have no trajectory and are not silently accepted as runs.
            if isinstance(value, dict) and isinstance(value.get("trajectory"), list):
                paths.append(path)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="*", type=Path)
    parser.add_argument("--glob", action="append", default=[], dest="patterns")
    parser.add_argument("--task-metadata", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = _expanded_paths(args.results, args.patterns)
    if not paths:
        parser.error("at least one result JSON is required")
    if args.output and args.output.resolve() in {path.resolve() for path in paths}:
        parser.error("analysis output must not overwrite an input result")
    contract = (
        load_analysis_contract(args.task_metadata) if args.task_metadata else None
    )
    runs: list[TrajectoryMetrics] = []
    for path in paths:
        try:
            runs.append(analyze_result_file(path, contract))
        except ValueError as exc:
            parser.error(str(exc))
    output = {
        "runs": [item.to_dict() for item in runs],
        "aggregate": aggregate_metrics(runs),
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
