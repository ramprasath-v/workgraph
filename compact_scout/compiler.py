"""Deterministic evidence-gated scout handoff compaction."""

from __future__ import annotations

import hashlib
import json

from scout.schema import ScoutHandoff

from .schema import CompactScoutKnowledge


def compile_compact_scout(handoff: ScoutHandoff) -> CompactScoutKnowledge:
    semantic_source = " ".join(
        [
            *handoff.observations,
            handoff.suspected_area,
            *handoff.recommended_investigation,
            *handoff.constraints,
        ]
    ).lower()
    has_bundled_resources = "bundled" in semantic_source and "resource" in semantic_source
    has_relative_location = "relative path" in semantic_source
    has_cwd_failure = (
        "current working directory" in semantic_source or "cwd" in semantic_source
    )
    has_package_location = (
        "installed package" in semantic_source
        or "importlib.resources" in semantic_source
    )
    has_explicit_override = (
        "resource_directory" in semantic_source
        and (
            "override" in semantic_source
            or "caller-supplied" in semantic_source
            or "when provided" in semantic_source
        )
    )
    has_output_constraint = (
        "existing report output" in semantic_source
        or "output format and content" in semantic_source
    )
    if not (has_bundled_resources and has_relative_location and has_cwd_failure):
        raise ValueError(
            "scout handoff lacks bundled-resource working-directory evidence"
        )
    if not (has_package_location and has_explicit_override and has_output_constraint):
        raise ValueError(
            "scout handoff lacks package-location, override, or output evidence"
        )

    semantic_payload = {
        "compact_scout_version": "0.1",
        "source_scout_handoff_id": handoff.scout_handoff_id,
        "principles": [
            (
                "Bundled resource lookup should remain independent of the "
                "process working directory."
            )
        ],
        "implementation_concepts": [
            (
                "Use a package-relative lookup for bundled defaults while "
                "preserving explicit caller-provided location overrides and "
                "existing output behavior."
            )
        ],
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
