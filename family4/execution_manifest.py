"""Deterministic builder for the frozen Family 4 execution manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from policy.v01 import public_overlap


PROTOCOL_PATH = Path(__file__).with_name("execution_protocol.json")
PREREGISTRATION_RELATIVE_PATH = Path(
    "preregistrations/family4_policy_v0_1.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load execution-manifest input: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("execution-manifest input must be an object")
    return value


def _load_transfer_candidates(
    repo_root: Path, specifications: list[dict[str, str]]
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for specification in specifications:
        path = repo_root / specification["artifact_path"]
        actual_hash = _sha256(path)
        if actual_hash != specification["artifact_sha256"]:
            raise ValueError("frozen historical transfer hash mismatch")
        artifact = _load_json(path)
        transfer_id = specification["transfer_knowledge_id"]
        if artifact.get("transfer_knowledge_id") != transfer_id:
            raise ValueError("frozen historical transfer identity mismatch")
        abstractions = artifact.get("principles", []) + artifact.get(
            "implementation_concepts", []
        )
        if not abstractions or not all(
            isinstance(value, str) and value for value in abstractions
        ):
            raise ValueError("frozen transfer has invalid portable abstractions")
        candidates[transfer_id] = {
            **specification,
            "portable_abstractions": abstractions,
            "existed_before_family4": True,
        }
    return candidates


def _rank_candidates(
    description: str,
    candidates: dict[str, dict[str, Any]],
    allowed_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    considered = []
    for transfer_id, candidate in candidates.items():
        if allowed_ids is not None and transfer_id not in allowed_ids:
            continue
        considered.append(
            {
                "transfer_knowledge_id": transfer_id,
                "artifact_path": candidate["artifact_path"],
                "artifact_sha256": candidate["artifact_sha256"],
                "existed_before_family4": True,
                "public_lexical_overlap": public_overlap(
                    description, tuple(candidate["portable_abstractions"])
                ),
            }
        )
    return sorted(
        considered,
        key=lambda value: (
            -value["public_lexical_overlap"],
            value["transfer_knowledge_id"],
        ),
    )


def _run_set(
    run_set_id: str,
    task_id: str,
    provider: str,
    model: str,
    repetitions: int,
    max_steps: int,
    context_mode: str,
    assistance_artifact: str | None = None,
) -> dict[str, Any]:
    return {
        "run_set_id": run_set_id,
        "task_id": task_id,
        "provider": provider,
        "model": model,
        "repetitions": repetitions,
        "max_steps": max_steps,
        "context_mode": context_mode,
        "assistance_artifact": assistance_artifact,
        "fresh_pristine_reset_each_run": True,
    }


def build_execution_manifest(
    repo_root: Path,
    protocol_path: Path = PROTOCOL_PATH,
) -> dict[str, Any]:
    """Build from frozen protocol, preregistration, and transfer abstractions only."""

    protocol = _load_json(protocol_path)
    preregistration_path = repo_root / PREREGISTRATION_RELATIVE_PATH
    preregistration_hash = _sha256(preregistration_path)
    if preregistration_hash != protocol["policy_preregistration_sha256"]:
        raise ValueError("Family 4 policy preregistration hash mismatch")
    preregistration = _load_json(preregistration_path)
    cases = {
        case["task_id"]: case
        for case in preregistration["cases"]
    }
    candidates = _load_transfer_candidates(
        repo_root, protocol["historical_transfer_candidates"]
    )
    retry_transfer_id = "transfer_93a42588ddd62085a6289d9b12613079"
    rankings: dict[str, list[dict[str, Any]]] = {}
    selections: dict[str, dict[str, Any]] = {}
    for task_id in protocol["target_models"]:
        allowed = {retry_transfer_id} if task_id == "task11_notification_retries" else None
        ranking = _rank_candidates(
            cases[task_id]["legal_policy_input"]["public_task_description"],
            candidates,
            allowed,
        )
        if not ranking:
            raise ValueError("historical transfer selection has no candidates")
        rankings[task_id] = ranking
        selections[task_id] = {
            **ranking[0],
            "selection_rationale": (
                "candidate identity already frozen in the Policy v0.1 preregistration"
                if task_id == "task11_notification_retries"
                else "highest deterministic public lexical overlap; transfer ID breaks ties"
            ),
            "policy_qualification_not_required": True,
        }

    repetitions = protocol["repetitions"]
    max_steps = protocol["max_steps"]
    escalation = protocol["escalation_protocol"]
    run_sets: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, str]] = {}
    for ordinal, task_id in enumerate(protocol["target_models"], start=10):
        short = f"task{ordinal}"
        target = protocol["target_models"][task_id]
        no_assistance = f"{short}_no_assistance"
        historical = f"{short}_historical_transfer"
        compact = f"{short}_compact_scout"
        escalate = f"{short}_escalate"
        run_sets[no_assistance] = _run_set(
            no_assistance,
            task_id,
            target["provider"],
            target["model"],
            repetitions,
            max_steps,
            "none",
        )
        run_sets[historical] = _run_set(
            historical,
            task_id,
            target["provider"],
            target["model"],
            repetitions,
            max_steps,
            "transfer_knowledge",
            selections[task_id]["artifact_path"],
        )
        run_sets[compact] = _run_set(
            compact,
            task_id,
            target["provider"],
            target["model"],
            repetitions,
            max_steps,
            "compact_scout",
            "TO_BE_ACQUIRED_UNDER_FROZEN_PROTOCOL",
        )
        run_sets[escalate] = _run_set(
            escalate,
            task_id,
            escalation["provider"],
            escalation["model"],
            escalation["repetitions"],
            escalation["max_steps"],
            "none",
        )
        policy_decision = cases[task_id]["policy_output"]["decision"]
        policy_run_set = (
            no_assistance if policy_decision == "NO_ASSISTANCE" else escalate
        )
        aliases[task_id] = {
            "POLICY_V0_1": policy_run_set,
            "ALWAYS_NO_ASSISTANCE": no_assistance,
            "ALWAYS_HISTORICAL_TRANSFER": historical,
            "ALWAYS_COMPACT_CURRENT_TASK_SCOUT": compact,
            "ALWAYS_ESCALATE": escalate,
        }

    return {
        "manifest_version": "0.1",
        "policy_preregistration_sha256": preregistration_hash,
        "policy_version": preregistration["policy_version"],
        "task_hashes": protocol["task_hashes"],
        "target_models": protocol["target_models"],
        "escalation_protocol": escalation,
        "repetitions": repetitions,
        "max_steps": max_steps,
        "historical_transfer_selection": {
            "procedure": (
                "For Tasks 10 and 12, score every pre-Family-4 frozen transfer "
                "with Policy v0.1 public_overlap and select the maximum, breaking "
                "ties by transfer ID. Task 11 retains its earlier frozen candidate."
            ),
            "candidate_universe_frozen_before_family4": True,
            "rankings": rankings,
            "assignments": selections,
        },
        "scout_acquisition_protocol": protocol["scout_acquisition_protocol"],
        "compact_scout_protocol": protocol["compact_scout_protocol"],
        "strategy_definitions": {
            "POLICY_V0_1": "execute the already-frozen policy decision without reevaluation",
            "ALWAYS_NO_ASSISTANCE": "target model from pristine state with no context artifact",
            "ALWAYS_HISTORICAL_TRANSFER": "target model from pristine state with its frozen assigned transfer regardless of qualification",
            "ALWAYS_COMPACT_CURRENT_TASK_SCOUT": "acquire one frozen detailed scout, compile deterministically, then run the target model from pristine state with that compact scout",
            "ALWAYS_ESCALATE": "frozen escalation model directly from pristine state with no assistance artifact or prior target attempt",
        },
        "unique_run_sets": run_sets,
        "strategy_run_set_aliases": aliases,
        "duplicate_execution_rule": (
            "Execute each unique run set once. Strategy labels that resolve to "
            "the same run-set ID reuse that exact frozen run set and are not "
            "treated as independent evidence."
        ),
        "pristine_reset": protocol["pristine_reset"],
        "generation_settings": {
            "target_models": {
                task_id: model["generation_settings"]
                for task_id, model in protocol["target_models"].items()
            },
            "escalation": escalation["generation_settings"],
            "scout": {
                "temperature": protocol["scout_acquisition_protocol"][
                    "temperature"
                ],
                "top_p": "omitted; provider default",
                "top_k": "omitted; provider default",
                "seed": "not exposed by the adapter",
            },
        },
        "accounting_definitions": {
            "target_execution": [
                "input_tokens",
                "output_tokens",
                "provider_total_tokens_when_available",
                "elapsed_seconds",
            ],
            "assistance_acquisition": [
                "detailed_scout_input_tokens",
                "detailed_scout_output_tokens",
                "detailed_scout_provider_total_tokens",
                "detailed_scout_elapsed_seconds",
            ],
            "compact_scout": (
                "zero model-inference cost; report artifact characters and "
                "estimated context tokens separately"
            ),
            "escalation": [
                "escalation_input_tokens",
                "escalation_output_tokens",
                "escalation_provider_total_tokens_when_available",
                "escalation_elapsed_seconds",
            ],
            "strategy_total": (
                "sum every inference component required to deploy the strategy"
            ),
            "scout_reuse_reporting": {
                "frozen_experiment_total": "one scout acquisition plus all five target executions",
                "per_new_task_deployment": "one scout acquisition plus one target execution",
            },
        },
        "primary_metrics": {
            "verified_success_rate": "verified successes divided by repetitions",
            "successes_per_repetitions": "integer successes and frozen denominator",
            "target_inference_tokens": "sum of target input, output, and provider totals reported separately",
            "total_inference_tokens": "all target, scout, and escalation inference required by the strategy",
            "elapsed_inference_time": "target, scout, and escalation elapsed time reported separately and in total",
            "escalation_rate": "runs executed by the escalation model divided by repetitions",
            "verification_use_rate": "runs with at least one run_tests tool action before the final deterministic evaluator divided by repetitions",
            "max_step_exhaustion_rate": "max-step-exhausted runs divided by repetitions",
            "malformed_output_rate": "malformed model-output steps divided by all agent steps",
            "invalid_tool_action_rate": "tool-validation-error actions divided by all tool actions",
            "relevant_source_read_write_rate": "runs reading or writing an analysis-contract relevant source divided by repetitions, reported separately for reads and writes",
            "unexpected_file_write_rate": "runs writing outside analysis-contract allowed outputs divided by repetitions",
            "passing_test_regression_count": "predeclared passing tests that fail after a run",
            "cost_per_verified_success": "strategy total cost divided by verified successes; null when successes are zero",
            "statistical_claims": "descriptive only; no significance claim from n=5",
        },
        "execution_order": protocol["execution_order"],
        "forbidden_adaptations": protocol["forbidden_adaptations"],
    }
