"""Generic deterministic compact-scout compiler frozen for Family 4."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath

from compact_scout.schema import CompactScoutKnowledge
from scout.schema import ScoutHandoff


COMPILER_VERSION = "family4-generic-0.1"
_PATCH_MARKERS = ("--- a/", "+++ b/", "@@ -", "```")
_FILE_PATTERN = re.compile(
    r"\b[\w./-]+\.(?:c|cc|cpp|cs|go|java|js|json|kt|php|py|rb|rs|swift|ts)\b",
    re.IGNORECASE,
)
_CALL_PATTERN = re.compile(r"\b[A-Za-z_]\w*\s*\([^\n)]*\)")
_IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z]+_[A-Za-z0-9_]+\b")
_TEST_IDENTIFIER_PATTERN = re.compile(r"\btest_[A-Za-z0-9_]+\b", re.IGNORECASE)


def _sanitize(line: str, inspected_files: tuple[str, ...]) -> str:
    if any(marker in line for marker in _PATCH_MARKERS):
        raise ValueError("compact scout source contains code or patch material")
    sanitized = line
    redactions = set()
    for relative in inspected_files:
        path = PurePosixPath(relative)
        redactions.update({relative, path.name, path.stem})
    for value in sorted(redactions, key=len, reverse=True):
        if value:
            sanitized = re.sub(
                rf"(?<![\w]){re.escape(value)}(?![\w])",
                "the relevant component",
                sanitized,
                flags=re.IGNORECASE,
            )
    sanitized = _FILE_PATTERN.sub("the relevant file", sanitized)
    sanitized = _CALL_PATTERN.sub("the relevant operation", sanitized)
    sanitized = _TEST_IDENTIFIER_PATTERN.sub("the relevant check", sanitized)
    sanitized = _IDENTIFIER_PATTERN.sub("the relevant identifier", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" -")
    if not sanitized:
        raise ValueError("compact scout source became empty after leakage filtering")
    return sanitized[:400]


def _unique(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
        if len(result) == limit:
            break
    return result


def compile_family4_compact_scout(
    handoff: ScoutHandoff,
) -> CompactScoutKnowledge:
    """Compact only allowed handoff fields without inference or task-specific rules."""

    inspected = tuple(handoff.files_inspected)
    observations = [
        _sanitize(value, inspected) for value in handoff.observations
    ]
    investigations = [
        _sanitize(value, inspected)
        for value in handoff.recommended_investigation
    ]
    constraints = [_sanitize(value, inspected) for value in handoff.constraints]
    suspected = _sanitize(handoff.suspected_area, inspected)
    principles = _unique(observations + constraints, 2)
    concepts = _unique(investigations + [suspected], 2)
    semantic_payload = {
        "compact_scout_version": "0.1",
        "source_scout_handoff_id": handoff.scout_handoff_id,
        "principles": principles,
        "implementation_concepts": concepts,
        "scout_provider": handoff.producer_provider,
        "scout_model": handoff.producer_model,
        "scout_input_tokens": handoff.input_tokens,
        "scout_output_tokens": handoff.output_tokens,
        "scout_total_tokens": handoff.total_tokens,
        "scout_elapsed_seconds": handoff.elapsed_seconds,
    }
    canonical = json.dumps(
        semantic_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    compact_id = f"compact_scout_{hashlib.sha256(canonical).hexdigest()[:32]}"
    return CompactScoutKnowledge.from_dict(
        {**semantic_payload, "compact_scout_id": compact_id}
    )
