"""Deterministic, leakage-free WorkGraph assistance-selection Policy v0.1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema import PolicyDecision, PolicyInput


SPEC_PATH = Path(__file__).with_name("policy_v0_1.json")
SOURCE_SUFFIXES = frozenset(
    {".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".kt", ".php", ".py", ".rb", ".rs", ".swift", ".ts"}
)
STOPWORDS = frozenset(
    {
        "after", "and", "are", "before", "but", "can", "correct", "current",
        "existing", "for", "from", "into", "must", "not", "only", "preserve",
        "should", "that", "the", "their", "this", "through", "when", "while",
        "with", "without",
    }
)


def load_policy_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Policy v0.1 specification: {exc}") from exc
    if not isinstance(value, dict) or value.get("policy_version") != "0.1":
        raise ValueError("invalid Policy v0.1 specification")
    thresholds = value.get("thresholds")
    rules = value.get("rules_in_order")
    if not isinstance(thresholds, dict) or not isinstance(rules, list) or len(rules) != 7:
        raise ValueError("Policy v0.1 specification is incomplete")
    return value


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        token
        for token in re.findall(r"[a-z][a-z0-9_]{2,}", text.casefold())
        if token not in STOPWORDS
    )


def public_overlap(task_description: str, abstractions: tuple[str, ...]) -> float:
    """Return an auditable overlap coefficient from public portable text only."""

    task_tokens = _tokens(task_description)
    artifact_tokens = _tokens(" ".join(abstractions))
    if not task_tokens or not artifact_tokens:
        return 0.0
    return round(
        len(task_tokens & artifact_tokens) / min(len(task_tokens), len(artifact_tokens)),
        6,
    )


def workspace_uncertainty(source_files: tuple[str, ...], spec: dict[str, Any]) -> str:
    """Classify structural uncertainty from paths and counts, never file contents."""

    thresholds = spec["thresholds"]
    count = len(source_files)
    source_types = {Path(path).suffix.casefold() for path in source_files}
    if count >= thresholds["high_source_file_count"] or len(source_types) >= 3:
        return "high"
    if count >= thresholds["medium_source_file_count"] or len(source_types) == 2:
        return "medium"
    return "low"


def source_files_from_workspace(workspace: Path) -> tuple[str, ...]:
    """Collect source paths without reading source or evaluator contents."""

    ignored_directories = {".git", ".pytest_cache", "__pycache__"}
    paths = []
    for path in workspace.rglob("*"):
        if not path.is_file() or any(part in ignored_directories for part in path.parts):
            continue
        relative = path.relative_to(workspace)
        name = relative.name.casefold()
        if path.suffix.casefold() not in SOURCE_SUFFIXES:
            continue
        if name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{relative.as_posix().casefold()}/":
            continue
        paths.append(relative.as_posix())
    return tuple(sorted(paths))


def decide(policy_input: PolicyInput) -> PolicyDecision:
    """Choose exactly one action before target-model execution."""

    spec = load_policy_spec()
    thresholds = spec["thresholds"]
    model = policy_input.target_model
    transfer = policy_input.historical_transfer
    scout = policy_input.compact_scout
    context_window = model.context_window_tokens
    transfer_ratio = round(transfer.estimated_context_tokens / context_window, 6)
    scout_ratio = round(scout.estimated_context_tokens / context_window, 6)
    overlap = public_overlap(
        policy_input.public_task_description,
        transfer.portable_abstractions,
    )
    uncertainty = workspace_uncertainty(policy_input.source_files, spec)
    language_supported = policy_input.task_language.casefold() in {
        language.casefold() for language in model.supported_languages
    }
    transfer_qualified = (
        transfer.available
        and transfer.verified
        and overlap >= thresholds["minimum_transfer_public_overlap"]
        and transfer_ratio <= thresholds["max_assistance_context_ratio"]
    )
    scout_qualified = (
        scout.available
        and scout.already_acquired
        and scout.condition_permits_use
        and scout.schema_valid
        and scout_ratio <= thresholds["max_assistance_context_ratio"]
    )
    signals = {
        "target_model_capability_tier": model.capability_tier,
        "target_language_supported": language_supported,
        "source_file_count": len(policy_input.source_files),
        "source_type_count": len(
            {Path(path).suffix.casefold() for path in policy_input.source_files}
        ),
        "workspace_uncertainty": uncertainty,
        "historical_transfer_available": transfer.available,
        "historical_transfer_verified": transfer.verified,
        "transfer_public_overlap": overlap,
        "transfer_context_ratio": transfer_ratio,
        "transfer_qualified": transfer_qualified,
        "compact_scout_available": scout.available,
        "compact_scout_already_acquired": scout.already_acquired,
        "compact_scout_permitted": scout.condition_permits_use,
        "compact_scout_context_ratio": scout_ratio,
        "compact_scout_qualified": scout_qualified,
    }

    if not language_supported:
        decision, code = "ESCALATE", "TARGET_LANGUAGE_UNSUPPORTED"
    elif model.capability_tier == "high":
        decision, code = "NO_ASSISTANCE", "HIGH_CAPABILITY_PRESERVE_UNAIDED"
    elif transfer_qualified:
        decision, code = (
            "HISTORICAL_TRANSFER",
            "VERIFIED_TRANSFER_HIGH_PUBLIC_OVERLAP",
        )
    elif scout_qualified:
        decision, code = (
            "COMPACT_CURRENT_TASK_SCOUT",
            "COMPACT_SCOUT_ALREADY_ACQUIRED",
        )
    elif model.capability_tier == "low":
        decision, code = (
            "ESCALATE",
            "LOW_CAPABILITY_WITHOUT_QUALIFIED_ASSISTANCE",
        )
    elif uncertainty == "high":
        decision, code = "ESCALATE", "HIGH_STRUCTURAL_UNCERTAINTY"
    else:
        decision, code = "NO_ASSISTANCE", "DEFAULT_PRESERVE_UNAIDED"
    return PolicyDecision("0.1", decision, signals, [code])
