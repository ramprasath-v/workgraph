"""Deterministic offline ingestion for retained Family 1/2 reproductions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .trajectory_metrics import aggregate_metrics, analyze_result_file


CONFIGS = {
    "family_1": {
        "reproduction_id": "f1r_task04_core_v1",
        "task_id": "task04_report_resources",
        "test_file": "test_report_renderer.py",
        "preregistration": "reproductions/family1_v1/preregistration.json",
        "manifest": "reproductions/family1_v1/evidence_manifest.json",
        "transfer": "transfer_knowledge/transfer_a4142b399f8684e6a75fda4a625ed4d8.json",
        "conditions": (
            ("F1R_BASELINE", "repeat_task04_report_resources_28b2a9415bb0"),
            ("F1R_RELEVANT_TRANSFER", "repeat_task04_report_resources_729e34487d81"),
        ),
        "classification": "FULL_REPRODUCTION",
        "classification_basis": "baseline 0/5 and relevant transfer 5/5",
    },
    "family_2": {
        "reproduction_id": "f2r_task07_core_v1",
        "task_id": "task07_retry_transfer",
        "test_file": "test_delivery_receiver.py",
        "preregistration": "reproductions/family2_v1/preregistration.json",
        "manifest": "reproductions/family2_v1/evidence_manifest.json",
        "transfer": "transfer_knowledge/transfer_93a42588ddd62085a6289d9b12613079.json",
        "conditions": (
            ("F2R_BASELINE", "repeat_task07_retry_transfer_769cbddc39d9"),
            ("F2R_RELEVANT_TRANSFER", "repeat_task07_retry_transfer_f0c2446e7222"),
        ),
        "classification": "NON_REPRODUCTION",
        "classification_basis": (
            "retained 0/5 to 5/5 harness outcomes materially contradict the "
            "historical 0/5 to 0/5 pattern"
        ),
    },
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _condition(repo_root: Path, condition_id: str, aggregate_id: str, test_file: str) -> dict[str, Any]:
    aggregate_relative = f"results/{aggregate_id}.json"
    run_relatives = [f"results/{aggregate_id}-run-{index:02d}.json" for index in range(1, 6)]
    aggregate_path = repo_root / aggregate_relative
    run_paths = [repo_root / relative for relative in run_relatives]
    aggregate = _load(aggregate_path)
    runs = [_load(path) for path in run_paths]
    if aggregate.get("aggregate_id") != aggregate_id:
        raise ValueError(f"aggregate identity mismatch: {aggregate_relative}")
    if [run.get("run_id") for run in runs] != [
        entry.get("run_id") for entry in aggregate.get("individual_runs", [])
    ]:
        raise ValueError(f"aggregate/run identity mismatch: {aggregate_relative}")
    identity_fields = (
        "task_id", "model_provider", "model_name", "context_mode",
        "transfer_knowledge_id", "max_steps",
    )
    expected_identity = {field: aggregate.get(field) for field in identity_fields}
    for run in runs:
        if {field: run.get(field) for field in identity_fields} != expected_identity:
            raise ValueError(f"run identity mismatch: {run.get('run_id')}")
    metrics = aggregate_metrics([analyze_result_file(path) for path in run_paths])
    successes = sum(run["success"] for run in runs)
    if successes != aggregate.get("successful_runs") or metrics["success_rate"] != aggregate.get("success_rate"):
        raise ValueError(f"raw/aggregate success mismatch: {aggregate_relative}")
    experiences = []
    for relative, run in zip(run_relatives, runs):
        experience_id = run.get("generated_experience_id")
        if experience_id is None:
            continue
        experience_relative = f"experiences/{experience_id}.json"
        experience_path = repo_root / experience_relative
        experience = _load(experience_path)
        if experience.get("experience_id") != experience_id or not experience.get("successful"):
            raise ValueError(f"generated experience mismatch: {experience_relative}")
        experiences.append({
            "source_run": relative,
            "experience_id": experience_id,
            "path": experience_relative,
            "sha256": _sha256(experience_path),
            "files_changed": experience.get("files_changed"),
            "verification": experience.get("verification"),
        })
    successful_writes = [
        entry.get("target")
        for run in runs for entry in run["trajectory"]
        if entry.get("action") == "write_file"
        and isinstance(entry.get("outcome"), str)
        and entry["outcome"].startswith("success")
    ]
    successful_reads = [
        entry.get("target")
        for run in runs for entry in run["trajectory"]
        if entry.get("action") == "read_file"
        and isinstance(entry.get("outcome"), str)
        and entry["outcome"].startswith("success")
    ]
    test_write_runs = sum(
        any(
            entry.get("action") == "write_file"
            and entry.get("target") == test_file
            and isinstance(entry.get("outcome"), str)
            and entry["outcome"].startswith("success")
            for entry in run["trajectory"]
        )
        for run in runs
    )
    return {
        "condition_id": condition_id,
        "identity": expected_identity,
        "aggregate": {
            "aggregate_id": aggregate_id,
            "path": aggregate_relative,
            "sha256": _sha256(aggregate_path),
        },
        "runs": [
            {
                "run_id": run["run_id"],
                "path": relative,
                "sha256": _sha256(path),
                "success": run["success"],
                "tests_passed": run["tests_passed"],
                "tests_failed": run["tests_failed"],
                "failure_type": run.get("failure_type"),
                "failure_message": run.get("failure_message"),
                "agent_steps": run["agent_steps"],
                "tool_calls": run["tool_calls"],
                "input_tokens": run["input_tokens"],
                "output_tokens": run["output_tokens"],
                "total_tokens": run["total_tokens"],
                "elapsed_seconds": run["elapsed_seconds"],
                "generated_experience_id": run.get("generated_experience_id"),
            }
            for relative, path, run in zip(run_relatives, run_paths, runs)
        ],
        "outcome": {
            "total_runs": len(runs),
            "successful_runs": successes,
            "failed_runs": len(runs) - successes,
            "success_rate": metrics["success_rate"],
            "final_tests_passed": [run["tests_passed"] for run in runs],
            "final_tests_failed": [run["tests_failed"] for run in runs],
            "failure_type_counts": aggregate.get("failure_type_counts"),
        },
        "trajectory_metrics": metrics,
        "directly_measured_file_behavior": {
            "unique_files_read": sorted({value for value in successful_reads if isinstance(value, str)}),
            "unique_files_written": sorted({value for value in successful_writes if isinstance(value, str)}),
            "test_file_written_run_count": test_write_runs,
            "unexpected_write_metric": None,
            "unexpected_write_note": "No predeclared analysis_contract exists for this task.",
        },
        "generated_experiences": experiences,
        "aggregate_elapsed": {
            "average_seconds": round(mean(run["elapsed_seconds"] for run in runs), 6),
            "min_seconds": min(run["elapsed_seconds"] for run in runs),
            "max_seconds": max(run["elapsed_seconds"] for run in runs),
        },
    }


def build_evidence_manifest(repo_root: Path, family_id: str) -> dict[str, Any]:
    """Build one manifest solely from frozen preregistration and retained JSON."""

    config = CONFIGS[family_id]
    prereg_path = repo_root / config["preregistration"]
    prereg = _load(prereg_path)
    if prereg.get("reproduction_id") != config["reproduction_id"]:
        raise ValueError("reproduction preregistration identity mismatch")
    conditions = [
        _condition(repo_root, condition_id, aggregate_id, config["test_file"])
        for condition_id, aggregate_id in config["conditions"]
    ]
    transfer_path = repo_root / config["transfer"]
    return {
        "evidence_manifest_version": "0.1",
        "family_id": family_id,
        "reproduction_id": config["reproduction_id"],
        "source_status": "new_retained_evidence_reproduction",
        "historical_observation": prereg["historical_observation"],
        "classification": {
            "value": config["classification"],
            "basis": config["classification_basis"],
            "rule_source": config["preregistration"],
        },
        "frozen_inputs": {
            "task_id": config["task_id"],
            "task_sha256": _tree_hash(repo_root / "tasks" / config["task_id"]),
            "preregistration_path": config["preregistration"],
            "preregistration_sha256": _sha256(prereg_path),
            "relevant_transfer_path": config["transfer"],
            "relevant_transfer_sha256": _sha256(transfer_path),
        },
        "conditions": conditions,
        "integrity_findings": {
            "all_raw_aggregate_identities_match": True,
            "all_generated_experience_references_resolve": True,
            "test_file_write_detected": any(
                condition["directly_measured_file_behavior"]["test_file_written_run_count"]
                for condition in conditions
            ),
            "interpretation": (
                "Harness-recorded success must not be treated as full pristine-suite verification when the test file was rewritten."
                if any(condition["directly_measured_file_behavior"]["test_file_written_run_count"] for condition in conditions)
                else "No retained trajectory wrote the task test file."
            ),
        },
    }
