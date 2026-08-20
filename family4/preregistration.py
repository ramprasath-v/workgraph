"""Build the deterministic, legal-input-only Family 4 policy preregistration."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from policy.schema import (
    CompactScoutCandidate,
    HistoricalTransferCandidate,
    PolicyInput,
    TargetModelProfile,
)
from policy.v01 import decide, source_files_from_workspace


METADATA_PATH = Path(__file__).with_name("public_metadata.json")
POLICY_SPEC_RELATIVE_PATH = Path("policy/policy_v0_1.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read Family 4 metadata: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Family 4 metadata must be an object")
    return value


def _transfer_input(
    repo_root: Path,
    candidate_metadata: object,
    task_description: str,
) -> tuple[HistoricalTransferCandidate, list[dict[str, Any]]]:
    if candidate_metadata is None:
        return HistoricalTransferCandidate(), []
    if not isinstance(candidate_metadata, dict):
        raise ValueError("historical transfer candidate must be an object or null")
    artifact_path = repo_root / candidate_metadata["artifact_path"]
    artifact_sha256 = _sha256(artifact_path)
    if artifact_sha256 != candidate_metadata["artifact_sha256"]:
        raise ValueError("historical transfer candidate hash mismatch")
    artifact = _load_json(artifact_path)
    if artifact.get("transfer_knowledge_id") != candidate_metadata.get(
        "transfer_knowledge_id"
    ):
        raise ValueError("historical transfer candidate identity mismatch")
    principles = artifact.get("principles")
    concepts = artifact.get("implementation_concepts")
    if not isinstance(principles, list) or not isinstance(concepts, list):
        raise ValueError("historical transfer candidate has invalid abstractions")
    abstractions = tuple(principles + concepts)
    rendered = " ".join(abstractions)
    estimated_tokens = math.ceil(len(rendered) / 4)
    transfer = HistoricalTransferCandidate(
        available=True,
        verified=candidate_metadata.get("verified"),
        portable_abstractions=abstractions,
        estimated_context_tokens=estimated_tokens,
    )
    considered = [
        {
            "artifact_path": candidate_metadata["artifact_path"],
            "artifact_sha256": artifact_sha256,
            "estimated_context_tokens": estimated_tokens,
            "portable_abstractions": list(abstractions),
            "transfer_knowledge_id": artifact["transfer_knowledge_id"],
            "verified": transfer.verified,
        }
    ]
    return transfer, considered


def _policy_input_dict(value: PolicyInput) -> dict[str, Any]:
    return {
        "public_task_description": value.public_task_description,
        "task_language": value.task_language,
        "source_files": list(value.source_files),
        "target_model": {
            "model_identity": value.target_model.model_identity,
            "capability_tier": value.target_model.capability_tier,
            "supported_languages": list(value.target_model.supported_languages),
            "context_window_tokens": value.target_model.context_window_tokens,
        },
        "historical_transfer": {
            "available": value.historical_transfer.available,
            "verified": value.historical_transfer.verified,
            "portable_abstractions": list(
                value.historical_transfer.portable_abstractions
            ),
            "estimated_context_tokens": (
                value.historical_transfer.estimated_context_tokens
            ),
        },
        "compact_scout": {
            "available": value.compact_scout.available,
            "already_acquired": value.compact_scout.already_acquired,
            "condition_permits_use": value.compact_scout.condition_permits_use,
            "schema_valid": value.compact_scout.schema_valid,
            "estimated_context_tokens": value.compact_scout.estimated_context_tokens,
        },
    }


def evaluate_policy_cases(
    repo_root: Path,
    metadata_path: Path = METADATA_PATH,
) -> list[dict[str, Any]]:
    """Evaluate only public metadata, workspace paths, and frozen abstractions."""

    metadata = _load_json(metadata_path)
    if metadata.get("metadata_version") != "0.1":
        raise ValueError("unsupported Family 4 metadata version")
    cases = metadata.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise ValueError("Family 4 requires exactly three metadata cases")
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Family 4 case metadata must be an object")
        task_id = case["task_id"]
        source_files = source_files_from_workspace(
            repo_root / "tasks" / task_id / "workspace"
        )
        transfer, considered = _transfer_input(
            repo_root,
            case.get("historical_transfer_candidate"),
            case["public_task_description"],
        )
        target = case["target_model"]
        scout = case["compact_scout"]
        policy_input = PolicyInput(
            public_task_description=case["public_task_description"],
            task_language=case["task_language"],
            source_files=source_files,
            target_model=TargetModelProfile(
                model_identity=target["model_identity"],
                capability_tier=target["capability_tier"],
                supported_languages=tuple(target["supported_languages"]),
                context_window_tokens=target["context_window_tokens"],
            ),
            historical_transfer=transfer,
            compact_scout=CompactScoutCandidate(
                available=scout["available"],
                already_acquired=scout["already_acquired"],
                condition_permits_use=scout["condition_permits_use"],
                schema_valid=scout["schema_valid"],
                estimated_context_tokens=scout["estimated_context_tokens"],
            ),
        )
        decision = decide(policy_input).to_dict()
        for candidate in considered:
            candidate["public_lexical_overlap"] = decision["signals"][
                "transfer_public_overlap"
            ]
            candidate["context_ratio"] = decision["signals"][
                "transfer_context_ratio"
            ]
        evaluated.append(
            {
                "task_id": task_id,
                "stratum": case["stratum"],
                "legal_policy_input": _policy_input_dict(policy_input),
                "workspace_structural_profile": {
                    "source_file_count": decision["signals"]["source_file_count"],
                    "source_type_count": decision["signals"]["source_type_count"],
                    "workspace_uncertainty": decision["signals"][
                        "workspace_uncertainty"
                    ],
                },
                "transfer_candidates_considered": considered,
                "policy_output": decision,
            }
        )
    return evaluated


def build_preregistration(repo_root: Path) -> dict[str, Any]:
    """Return the complete deterministic preregistration without writing files."""

    policy_spec_path = repo_root / POLICY_SPEC_RELATIVE_PATH
    return {
        "preregistration_version": "0.1",
        "policy_version": "0.1",
        "policy_spec_sha256": _sha256(policy_spec_path),
        "decision_timing": "before any Family 4 target-model execution",
        "hypothesis": (
            "A leakage-free assistance-selection policy can outperform "
            "unconditional assistance by preserving unaided success when the "
            "model is already sufficient while still using assistance or "
            "escalation when unaided capability is uncertain or insufficient."
        ),
        "cases": evaluate_policy_cases(repo_root),
        "future_conditions": [
            "POLICY_V0_1",
            "ALWAYS_NO_ASSISTANCE",
            "ALWAYS_HISTORICAL_TRANSFER",
            "ALWAYS_COMPACT_CURRENT_TASK_SCOUT",
            "ALWAYS_ESCALATE",
        ],
        "primary_outcomes": [
            "verified_task_success",
            "total_inference_tokens",
            "elapsed_time",
            "escalation_rate",
            "unexpected_file_write_rate",
            "passing_test_regression_count",
            "cost_per_verified_success",
        ],
        "cost_accounting": (
            "Include frozen scout and escalation acquisition costs whenever "
            "the applicable condition incurs them."
        ),
    }
