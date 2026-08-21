"""Deterministic preregistration for the Task 09 assistance ablation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from harness.assistance_control import (
    approximate_tokens,
    load_assistance_control,
    payload_sha256,
)
from harness.verification_integrity import INTEGRITY_GUARD_VERSION


ABLATION_ID = "family3_task09_assistance_interference_v1"
TASK_ID = "task09_role_changes"
ROOT = Path("reproductions/family3_task09_ablation_v1")
CONTROL_PATHS = (
    ROOT / "empty_assistance_wrapper.json",
    ROOT / "neutral_length_matched_context.json",
    ROOT / "relevant_principle_no_authority.json",
)
TRANSFER_PATH = Path(
    "transfer_knowledge/transfer_6b80e8c84cf89a2f7ceec3a2278cf531.json"
)
GUARD_FILES = (
    "harness/verification_integrity.py",
    "harness/assistance_control.py",
    "harness/prompting.py",
    "harness/runner.py",
    "harness/metrics.py",
    "harness/repeated.py",
)


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


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_preregistration(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    controls = [load_assistance_control(repo_root / path) for path in CONTROL_PATHS]
    if [control.condition_id for control in controls] != [
        "EMPTY_ASSISTANCE_WRAPPER",
        "NEUTRAL_LENGTH_MATCHED_CONTEXT",
        "RELEVANT_PRINCIPLE_NO_AUTHORITY",
    ]:
        raise ValueError("ablation controls have incorrect order or identity")
    if len({control.wrapper_template_id for control in controls}) != 1:
        raise ValueError("ablation controls must use one wrapper template")
    if any(control.protected_evaluator_files != ("test_role_index.py",) for control in controls):
        raise ValueError("Task 09 evaluator protection is incomplete")

    transfer = _load(repo_root / TRANSFER_PATH)
    reference_payload = "\n".join(
        [*transfer["principles"], *transfer["implementation_concepts"]]
    )
    if controls[2].payload != reference_payload:
        raise ValueError("no-authority payload is not the exact portable principle")
    if controls[1].payload_character_count != len(reference_payload):
        raise ValueError("neutral payload is not character-length matched")
    if controls[1].payload_approximate_tokens != approximate_tokens(reference_payload):
        raise ValueError("neutral payload is not approximately token matched")
    serialized_payloads = "\n".join(control.payload for control in controls).lower()
    for forbidden in (
        "task09", "test_role_index", "membership_registry", "role_index.py",
        "analysis_contract", "change_role", "role_summary",
    ):
        if forbidden in serialized_payloads:
            raise ValueError("ablation payload leaks Task 09 identifiers")

    common_command = [
        "python3", "-m", "harness.runner",
        "--task", TASK_ID,
        "--provider", "transformers",
        "--model", "Qwen/Qwen2.5-7B-Instruct",
        "--max-steps", "8",
        "--repeat", "5",
    ]
    conditions = []
    for control_path, control in zip(CONTROL_PATHS, controls):
        conditions.append({
            "condition_id": control.condition_id,
            "assistance_control_id": control.assistance_control_id,
            "control_path": control_path.as_posix(),
            "control_sha256": _sha256(repo_root / control_path),
            "wrapper_template_id": control.wrapper_template_id,
            "payload": control.payload,
            "payload_sha256": control.payload_sha256,
            "payload_character_count": control.payload_character_count,
            "payload_approximate_tokens": control.payload_approximate_tokens,
            "protected_evaluator_files": list(control.protected_evaluator_files),
            "command": common_command + ["--assistance-control", control_path.as_posix()],
        })

    return {
        "ablation_id": ABLATION_ID,
        "ablation_version": "0.1",
        "status": "preregistered_not_executed",
        "task": {
            "task_id": TASK_ID,
            "sha256": _tree_hash(repo_root / "tasks" / TASK_ID),
            "analysis_contract_model_visible": False,
        },
        "target": {
            "provider": "transformers",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "max_steps": 8,
            "repeat": 5,
        },
        "generation_settings": {
            "TRANSFORMERS_TEMPERATURE": "0",
            "TRANSFORMERS_MAX_NEW_TOKENS": "512",
            "temperature": 0,
            "do_sample": False,
            "max_new_tokens": 512,
            "top_p": "not passed",
            "top_k": "not passed",
            "seed": "not used",
            "independence_note": (
                "Repeated runs may be effectively deterministic and are not "
                "treated as independent statistical samples."
            ),
        },
        "verification_integrity": {
            "guard_version": INTEGRITY_GUARD_VERSION,
            "guard_files": {
                path: _sha256(repo_root / path) for path in GUARD_FILES
            },
            "protected_evaluators": {
                "test_role_index.py": _sha256(
                    repo_root / "tasks" / TASK_ID / "workspace" / "test_role_index.py"
                )
            },
            "success_rule": (
                "evaluator return code passes and every protected evaluator hash "
                "matches its pre-run hash"
            ),
        },
        "retained_anchors_not_rerun": [
            {
                "condition": "BASELINE_NO_ASSISTANCE",
                "aggregate_id": "repeat_task09_role_changes_696038d25c92",
                "path": "results/repeat_task09_role_changes_696038d25c92.json",
                "sha256": _sha256(repo_root / "results/repeat_task09_role_changes_696038d25c92.json"),
                "successful_runs": 5,
            },
            {
                "condition": "AUTHORITATIVE_RELEVANT_TRANSFER",
                "aggregate_id": "repeat_task09_role_changes_d826c0ae1567",
                "path": "results/repeat_task09_role_changes_d826c0ae1567.json",
                "sha256": _sha256(repo_root / "results/repeat_task09_role_changes_d826c0ae1567.json"),
                "successful_runs": 0,
                "transfer_path": TRANSFER_PATH.as_posix(),
                "transfer_sha256": _sha256(repo_root / TRANSFER_PATH),
                "reference_semantic_payload_sha256": payload_sha256(reference_payload),
                "reference_semantic_payload_character_count": len(reference_payload),
                "reference_semantic_payload_approximate_tokens": approximate_tokens(reference_payload),
            },
        ],
        "prompt_control": {
            "wrapper_template_id": controls[0].wrapper_template_id,
            "constant_components": [
                "public task prompt", "tool schema", "system instructions",
                "assistance section position", "wrapper labels", "model settings",
                "pristine task state", "step budget",
            ],
            "intended_variable": "exact assistance payload text and its control metadata",
        },
        "conditions_in_execution_order": conditions,
        "execution_order_rule": (
            "Run each condition five times in listed order and preserve its raw "
            "evidence before starting the next; do not adapt after outcomes."
        ),
        "interpretation_rules": {
            "PATTERN_1": "Empty wrapper fails similarly to authoritative transfer: assistance pathway/template effect becomes a strong candidate.",
            "PATTERN_2": "Empty wrapper succeeds and neutral context fails: context/token-load or added-context perturbation becomes a strong candidate.",
            "PATTERN_3": "Empty and neutral succeed and no-authority relevant principle fails: semantic content/interference becomes a stronger candidate.",
            "PATTERN_4": "All three new conditions succeed while authoritative relevant transfer remains failed: authority/provenance framing becomes a strong candidate.",
            "PATTERN_5": "Mixed or inconsistent outcomes: mechanism remains unresolved; consider placement/formulation ablation next.",
            "causal_claims_allowed": False,
        },
        "retention": {
            "per_condition": {"run_json": 5, "aggregate_json": 1},
            "retain": [
                "full trajectory", "test counts", "integrity fields and hashes",
                "condition and context identity", "payload hash", "model/provider",
                "steps/tool calls", "tokens", "elapsed time",
                "generated experiences if any",
            ],
            "raw_immutability": "Do not rename or rewrite raw result JSON.",
            "postexecution_manifest": (
                "reproductions/family3_task09_ablation_v1/evidence_manifest.json"
            ),
        },
        "forbidden_actions": [
            "rerun retained anchors", "run Family 4", "modify Task 09",
            "expose analysis_contract to the model", "tune after outcomes",
        ],
    }
