"""Deterministic evidence projection for the WorkGraph paper-readiness review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CHECKPOINT_RELATIVE_PATH = Path("analysis/cross_family_checkpoint.json")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load frozen checkpoint: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("frozen checkpoint must be an object")
    return value


def build_paper_evidence(repo_root: Path) -> dict[str, Any]:
    """Project the frozen checkpoint without reconstructing missing evidence."""

    checkpoint_path = repo_root / CHECKPOINT_RELATIVE_PATH
    checkpoint = _load_json(checkpoint_path)
    families = checkpoint.get("families")
    if not isinstance(families, list) or len(families) != 3:
        raise ValueError("paper evidence requires the frozen three-family checkpoint")
    projected = []
    for family in families:
        if family["family_id"] in {"family_1", "family_2"}:
            projected.append(
                {
                    "family_id": family["family_id"],
                    "task_id": family["task_id"],
                    "evidence_status": "historical_observation_without_raw_results",
                    "raw_per_run_evidence_retained": False,
                    "machine_derived": False,
                    "historical_observation": family["historical_observation"],
                    "condition_metrics": None,
                }
            )
            continue
        conditions = []
        for condition in family["conditions"]:
            conditions.append(
                {
                    "condition_id": condition["condition_id"],
                    "label": condition["label"],
                    "outcome": condition["outcome"],
                    "target_model_efficiency": condition["qwen_only_efficiency"],
                    "total_inference_accounting": condition[
                        "persisted_total_inference_accounting"
                    ],
                    "trajectory_metrics": condition["trajectory_metrics"],
                    "retention_status": condition["retention_status"],
                }
            )
        projected.append(
            {
                "family_id": family["family_id"],
                "task_id": family["task_id"],
                "evidence_status": "machine_derived_from_complete_frozen_raw_results",
                "raw_per_run_evidence_retained": True,
                "machine_derived": True,
                "condition_metrics": conditions,
            }
        )
    return {
        "paper_evidence_version": "0.1",
        "source_checkpoint": CHECKPOINT_RELATIVE_PATH.as_posix(),
        "source_checkpoint_sha256": hashlib.sha256(
            checkpoint_path.read_bytes()
        ).hexdigest(),
        "families": projected,
        "evidence_rule": (
            "Families 1 and 2 remain historical observations with null machine "
            "metrics; only Family 3 numerical values are projected."
        ),
    }
