"""Build the deterministic Families 1-3 research checkpoint from frozen JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .trajectory_metrics import (
    aggregate_metrics,
    analyze_result_file,
    load_analysis_contract,
)


RETAINED = "complete_raw_and_aggregate"
NOT_RETAINED = "raw_results_not_retained"
IDENTITY_FIELDS = (
    "task_id",
    "model_provider",
    "model_name",
    "context_mode",
    "transfer_knowledge_id",
    "scout_handoff_id",
    "compact_scout_id",
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"checkpoint input does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read checkpoint input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"checkpoint input must be a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _explicit_relative_path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"{name} must be an explicit repository-relative path")
    if any(character in value for character in "*?[]"):
        raise ValueError(f"{name} must not contain a glob")
    return value


def _validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("checkpoint_version") != "0.1":
        raise ValueError("unsupported cross-family checkpoint version")
    families = manifest.get("families")
    if not isinstance(families, list) or len(families) != 3:
        raise ValueError("manifest must explicitly define three families")
    expected_families = ["family_1", "family_2", "family_3"]
    if [family.get("family_id") for family in families] != expected_families:
        raise ValueError("manifest families must be explicit and ordered")
    for family in families:
        conditions = family.get("conditions")
        if not isinstance(conditions, list) or len(conditions) != 5:
            raise ValueError("each family must explicitly define five conditions")
        identifiers = [condition.get("condition_id") for condition in conditions]
        if len(set(identifiers)) != 5 or not all(
            isinstance(identifier, str) for identifier in identifiers
        ):
            raise ValueError("condition identifiers must be explicit and unique")
        for condition in conditions:
            status = condition.get("retention_status")
            runs = condition.get("run_results")
            aggregate = condition.get("aggregate_result")
            if status == NOT_RETAINED:
                if aggregate is not None or runs != []:
                    raise ValueError("unretained conditions must not claim result paths")
            elif status == RETAINED:
                _explicit_relative_path(aggregate, "aggregate_result")
                if not isinstance(runs, list) or len(runs) != 5:
                    raise ValueError("retained conditions require five explicit runs")
                for path in runs:
                    _explicit_relative_path(path, "run_result")
                expected = condition.get("expected_identity")
                if not isinstance(expected, dict) or set(expected) != set(
                    IDENTITY_FIELDS
                ):
                    raise ValueError("retained condition identity is incomplete")
            else:
                raise ValueError("unknown retention status")
    return families


def _check_identity(value: dict[str, Any], expected: dict[str, Any], path: str) -> None:
    actual = {field: value.get(field) for field in IDENTITY_FIELDS}
    if actual != expected:
        raise ValueError(f"condition identity mismatch in {path}")


def _retained_condition(
    repo_root: Path,
    condition: dict[str, Any],
    analysis_contract_path: str | None,
) -> dict[str, Any]:
    aggregate_relative = _explicit_relative_path(
        condition["aggregate_result"], "aggregate_result"
    )
    run_relatives = [
        _explicit_relative_path(path, "run_result")
        for path in condition["run_results"]
    ]
    aggregate_path = repo_root / aggregate_relative
    run_paths = [repo_root / path for path in run_relatives]
    aggregate = _load_json(aggregate_path)
    runs = [_load_json(path) for path in run_paths]
    expected = condition["expected_identity"]
    _check_identity(aggregate, expected, aggregate_relative)
    for relative, run in zip(run_relatives, runs):
        _check_identity(run, expected, relative)

    configured_ids = [run.get("run_id") for run in runs]
    aggregate_runs = aggregate.get("individual_runs")
    if not isinstance(aggregate_runs, list):
        raise ValueError(f"aggregate has no individual_runs: {aggregate_relative}")
    aggregate_ids = [entry.get("run_id") for entry in aggregate_runs]
    if configured_ids != aggregate_ids:
        raise ValueError(f"aggregate/raw run mismatch: {aggregate_relative}")

    contract = None
    if analysis_contract_path is not None:
        relative = _explicit_relative_path(
            analysis_contract_path, "analysis_contract"
        )
        contract = load_analysis_contract(repo_root / relative)
    measured = [
        analyze_result_file(path, contract) for path in run_paths
    ]
    trajectory = aggregate_metrics(measured)
    comparisons = {
        "number_of_runs": aggregate.get("total_runs"),
        "success_rate": aggregate.get("success_rate"),
        "mean_agent_steps": aggregate.get("average_agent_steps"),
        "mean_tool_calls": aggregate.get("average_tool_calls"),
        "mean_input_tokens": aggregate.get("average_input_tokens"),
        "mean_output_tokens": aggregate.get("average_output_tokens"),
        "mean_total_tokens": aggregate.get("average_total_tokens"),
        "mean_elapsed_seconds": aggregate.get("average_elapsed_seconds"),
    }
    for metric, persisted in comparisons.items():
        if trajectory[metric] != persisted:
            raise ValueError(
                f"raw/aggregate metric mismatch for {metric}: {aggregate_relative}"
            )

    successes = sum(bool(run.get("success")) for run in runs)
    if successes != aggregate.get("successful_runs"):
        raise ValueError(f"success count mismatch: {aggregate_relative}")
    raw_total_inference_tokens = [
        run.get("total_inference_tokens") for run in runs
    ]
    raw_total_inference_elapsed = [
        run.get("total_inference_elapsed_seconds") for run in runs
    ]
    if not all(isinstance(value, (int, float)) for value in (
        *raw_total_inference_tokens,
        *raw_total_inference_elapsed,
    )):
        raise ValueError(f"invalid total inference accounting: {aggregate_relative}")
    if round(mean(raw_total_inference_tokens), 6) != aggregate.get(
        "average_total_inference_tokens"
    ):
        raise ValueError(f"total token accounting mismatch: {aggregate_relative}")
    if round(mean(raw_total_inference_elapsed), 6) != aggregate.get(
        "average_total_inference_elapsed_seconds"
    ):
        raise ValueError(f"total elapsed accounting mismatch: {aggregate_relative}")

    evidence_paths = [aggregate_relative, *run_relatives]
    return {
        "condition_id": condition["condition_id"],
        "label": condition["label"],
        "retention_status": RETAINED,
        "evidence": {
            "aggregate_result": aggregate_relative,
            "run_results": run_relatives,
            "sha256": {
                path: _sha256(repo_root / path) for path in evidence_paths
            },
        },
        "outcome": {
            "total_runs": len(runs),
            "successful_runs": successes,
            "failed_runs": len(runs) - successes,
            "success_rate": trajectory["success_rate"],
        },
        "qwen_only_efficiency": {
            "mean_input_tokens": trajectory["mean_input_tokens"],
            "mean_output_tokens": trajectory["mean_output_tokens"],
            "mean_total_tokens": trajectory["mean_total_tokens"],
            "mean_elapsed_seconds": trajectory["mean_elapsed_seconds"],
        },
        "persisted_total_inference_accounting": {
            "scout_input_tokens": aggregate.get("scout_input_tokens"),
            "scout_output_tokens": aggregate.get("scout_output_tokens"),
            "scout_total_tokens": aggregate.get("scout_total_tokens"),
            "scout_elapsed_seconds": aggregate.get("scout_elapsed_seconds"),
            "average_total_inference_tokens": aggregate.get(
                "average_total_inference_tokens"
            ),
            "average_total_inference_elapsed_seconds": aggregate.get(
                "average_total_inference_elapsed_seconds"
            ),
            "frozen_experiment_total_inference_tokens": aggregate.get(
                "frozen_experiment_total_inference_tokens"
            ),
            "frozen_experiment_total_inference_elapsed_seconds": aggregate.get(
                "frozen_experiment_total_inference_elapsed_seconds"
            ),
            "estimated_deployment_total_inference_tokens": aggregate.get(
                "estimated_deployment_total_inference_tokens"
            ),
            "estimated_deployment_total_inference_elapsed_seconds": aggregate.get(
                "estimated_deployment_total_inference_elapsed_seconds"
            ),
        },
        "trajectory_metrics": trajectory,
    }


def build_checkpoint(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    """Build a checkpoint without mutating any input artifact."""

    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    families = _validate_manifest(manifest)
    rendered_families = []
    for family in families:
        conditions = []
        for condition in family["conditions"]:
            if condition["retention_status"] == NOT_RETAINED:
                conditions.append(
                    {
                        "condition_id": condition["condition_id"],
                        "label": condition["label"],
                        "retention_status": NOT_RETAINED,
                        "evidence": None,
                        "outcome": None,
                        "qwen_only_efficiency": None,
                        "persisted_total_inference_accounting": None,
                        "trajectory_metrics": None,
                    }
                )
            else:
                conditions.append(
                    _retained_condition(
                        repo_root,
                        condition,
                        family.get("analysis_contract"),
                    )
                )
        rendered_families.append(
            {
                "family_id": family["family_id"],
                "domain": family["domain"],
                "task_id": family["task_id"],
                "evidence_level": (
                    "complete_raw_and_aggregate"
                    if all(
                        item["retention_status"] == RETAINED for item in conditions
                    )
                    else "historical_observation_without_raw_results"
                ),
                "historical_observation": family.get("historical_observation"),
                "conditions": conditions,
            }
        )

    family_3 = rendered_families[2]
    baseline, *assisted = family_3["conditions"]
    interference_observed = (
        baseline["outcome"]["success_rate"] > 0
        and all(item["outcome"]["success_rate"] == 0 for item in assisted)
    )
    return {
        "checkpoint_version": manifest["checkpoint_version"],
        "source_manifest": manifest_path.relative_to(repo_root).as_posix(),
        "source_manifest_sha256": _sha256(manifest_path),
        "families": rendered_families,
        "observed_outcome_classes": [
            {
                "class": "capability_enabling_assistance",
                "family_id": "family_1",
                "machine_derived": False,
                "evidence_limitation": "original Task 04 raw results not retained",
            },
            {
                "class": "assistance_insufficient",
                "family_id": "family_2",
                "machine_derived": False,
                "evidence_limitation": "original Task 07 raw results not retained",
            },
            {
                "class": "assistance_induced_interference",
                "family_id": "family_3",
                "machine_derived": interference_observed,
                "evidence_limitation": None,
            },
        ],
        "predeclared_next_hypothesis": (
            "A policy that decides whether to use no assistance, historical "
            "verified experience, current-task scouting, or model escalation can "
            "outperform unconditional experience injection in reliability and/or "
            "resource efficiency."
        ),
        "falsified_naive_hypothesis": (
            "If retrieved guidance is relevant and correct, injecting it cannot hurt."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("analysis/cross_family_manifest.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    checkpoint = build_checkpoint(root, manifest)
    rendered = json.dumps(checkpoint, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        input_paths = {
            (root / path).resolve()
            for family in checkpoint["families"]
            for condition in family["conditions"]
            if condition["evidence"] is not None
            for path in (
                [condition["evidence"]["aggregate_result"]]
                + condition["evidence"]["run_results"]
            )
        }
        if output.resolve() in input_paths or output.resolve() == manifest.resolve():
            parser.error("checkpoint output must not overwrite an input")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
