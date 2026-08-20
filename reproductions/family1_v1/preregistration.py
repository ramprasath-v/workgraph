"""Deterministic preregistration builder for Family 1 reproduction v1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPRODUCTION_ID = "f1r_task04_core_v1"
TASK_ID = "task04_report_resources"
TRANSFER_ID = "transfer_a4142b399f8684e6a75fda4a625ed4d8"
TRANSFER_PATH = Path(
    "transfer_knowledge/transfer_a4142b399f8684e6a75fda4a625ed4d8.json"
)
RECIPE_PATH = Path("recipes/recipe_98832e7c414d8cb42300e4dbc80d7535.json")
EXPERIENCE_PATH = Path(
    "experiences/exp_aedf873f3b13471ea3e0145e4a4c7c2d.json"
)
HARNESS_FILES = (
    "harness/prompting.py",
    "harness/agent.py",
    "harness/action_normalization.py",
    "harness/tools.py",
    "harness/runner.py",
    "harness/transformers_adapter.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and ".pytest_cache" not in path.parts
        ):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _combined_harness_hash(repo_root: Path) -> str:
    digest = hashlib.sha256()
    for relative in HARNESS_FILES:
        path = repo_root / relative
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_preregistration(repo_root: Path) -> dict[str, Any]:
    """Build without reading benchmark results or invoking a provider."""

    transfer_path = repo_root / TRANSFER_PATH
    recipe_path = repo_root / RECIPE_PATH
    experience_path = repo_root / EXPERIENCE_PATH
    transfer = _load_json(transfer_path)
    recipe = _load_json(recipe_path)
    experience = _load_json(experience_path)
    if transfer.get("transfer_knowledge_id") != TRANSFER_ID:
        raise ValueError("Family 1 reproduction transfer identity mismatch")
    if transfer.get("source_recipe_id") != recipe.get("recipe_id"):
        raise ValueError("Family 1 transfer-to-recipe provenance mismatch")
    if recipe.get("source_experience_id") != experience.get("experience_id"):
        raise ValueError("Family 1 recipe-to-experience provenance mismatch")
    if recipe.get("task_id") != "task02_config_path":
        raise ValueError("Family 1 transfer is not derived from frozen Task 02")
    if not experience.get("successful") or experience.get("task_id") != (
        "task02_config_path"
    ):
        raise ValueError("Family 1 source experience is not verified Task 02 evidence")
    serialized_transfer = json.dumps(transfer, sort_keys=True).lower()
    for forbidden in (
        "task04",
        "report_renderer",
        "load_render_defaults",
        "render_report",
        "defaults.json",
        "--- a/",
        "+++ b/",
        "@@ -",
    ):
        if forbidden in serialized_transfer:
            raise ValueError("Family 1 transfer contains Task 04 or patch leakage")

    common_command = [
        "python3",
        "-m",
        "harness.runner",
        "--task",
        TASK_ID,
        "--provider",
        "transformers",
        "--model",
        "Qwen/Qwen2.5-7B-Instruct",
        "--max-steps",
        "8",
        "--repeat",
        "5",
    ]
    file_hashes = {
        relative: _sha256(repo_root / relative) for relative in HARNESS_FILES
    }
    return {
        "reproduction_id": REPRODUCTION_ID,
        "reproduction_version": "0.1",
        "evidence_status": "new_retained_evidence_reproduction_not_original_recovery",
        "source_family": "family_1",
        "consumer_task": TASK_ID,
        "historical_observation": {
            "baseline_successes": 0,
            "relevant_transfer_successes": 5,
            "repetitions": 5,
            "machine_recomputed": False,
            "original_raw_evidence_retained": False,
        },
        "target": {
            "provider": "transformers",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "max_steps": 8,
            "repetitions": 5,
        },
        "generation_settings": {
            "TRANSFORMERS_TEMPERATURE": "0",
            "TRANSFORMERS_MAX_NEW_TOKENS": "512",
            "temperature": 0,
            "do_sample": False,
            "max_new_tokens": 512,
            "top_p": "not passed",
            "top_k": "not passed",
            "seed": "not passed or used because sampling is disabled",
            "replication_note": (
                "Repeated trajectories may be identical and are not assumed to "
                "be statistically independent."
            ),
        },
        "frozen_inputs": {
            "task_hash": _tree_hash(repo_root / "tasks" / TASK_ID),
            "transfer": {
                "transfer_knowledge_id": TRANSFER_ID,
                "path": TRANSFER_PATH.as_posix(),
                "sha256": _sha256(transfer_path),
                "source_recipe_id": recipe["recipe_id"],
                "source_recipe_path": RECIPE_PATH.as_posix(),
                "source_recipe_sha256": _sha256(recipe_path),
                "source_experience_id": experience["experience_id"],
                "source_experience_path": EXPERIENCE_PATH.as_posix(),
                "source_experience_sha256": _sha256(experience_path),
                "source_experience_verified": True,
            },
            "harness": {
                "combined_sha256": _combined_harness_hash(repo_root),
                "files": file_hashes,
            },
        },
        "conditions_in_execution_order": [
            {
                "condition_id": "F1R_BASELINE",
                "context_mode": "none",
                "transfer_knowledge_id": None,
                "command": common_command,
            },
            {
                "condition_id": "F1R_RELEVANT_TRANSFER",
                "context_mode": "transfer_knowledge",
                "transfer_knowledge_id": TRANSFER_ID,
                "command": common_command
                + ["--transfer-knowledge", TRANSFER_PATH.as_posix()],
            },
        ],
        "no_adaptation_rule": (
            "After baseline execution, do not change the task, transfer, prompt, "
            "harness, generation settings, max steps, repetitions, or condition order."
        ),
        "pristine_reset": {
            "source": "exact frozen Task 04 workspace",
            "fresh_reset_before_every_repetition": True,
            "task_hash_check_before_reproduction": True,
            "task_hash_check_after_reproduction": True,
            "state_carryover_allowed": False,
        },
        "retention": {
            "expected_primary_files_per_condition": {
                "individual_result_json": 5,
                "aggregate_json": 1,
            },
            "result_location": "results/",
            "postexecution_manifest": (
                "reproductions/family1_v1/evidence_manifest.json"
            ),
            "manifest_fields": [
                "condition identity and exact aggregate/run paths",
                "SHA-256 for every aggregate and run JSON",
                "task hash before and after",
                "transfer and harness hashes",
                "generation settings",
                "any normally generated verified-experience side artifacts",
            ],
            "immutability_rule": (
                "Do not rename or rewrite result JSON after creation. Retain and "
                "hash any generated experience, but do not compile or inject it."
            ),
        },
        "offline_analysis": {
            "analyzer": "analysis.trajectory_metrics",
            "retroactive_analysis_contract": False,
            "metrics": [
                "success_rate",
                "final_tests_passed_failed",
                "verification_use_rate",
                "revision_after_failure_rate",
                "max_step_exhaustion_rate",
                "malformed_output_rate",
                "invalid_tool_action_rate",
                "repeated_identical_actions",
                "agent_steps",
                "tool_calls",
                "input_output_total_tokens",
                "elapsed_seconds",
            ],
        },
        "classification_rule": {
            "FULL_REPRODUCTION": "baseline 0/5 and relevant transfer 5/5",
            "PARTIAL_REPRODUCTION": (
                "relevant transfer materially improves success without the exact "
                "0/5 to 5/5 pattern"
            ),
            "NON_REPRODUCTION": "no meaningful success improvement",
            "thresholds_frozen_before_execution": True,
        },
        "forbidden_conditions": [
            "irrelevant transfer",
            "detailed scout",
            "compact scout",
            "new scout acquisition",
            "new transfer generation",
            "Family 4 execution",
        ],
    }
