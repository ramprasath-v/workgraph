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
    resource_profile = (
        has_bundled_resources
        and has_relative_location
        and has_cwd_failure
        and has_package_location
        and has_explicit_override
        and has_output_constraint
    )

    has_retry_delivery = "redelivery" in semantic_source or "retry" in semantic_source
    has_completed_identity = (
        "previously processed" in semantic_source
        or "has been processed" in semantic_source
    )
    has_recorded_outcome = (
        "previously stored response" in semantic_source
        or "corresponding responses" in semantic_source
        or "associated responses" in semantic_source
    )
    has_duplicate_side_effect = (
        "new shipment" in semantic_source
        and ("redelivery" in semantic_source or "same" in semantic_source)
    )
    has_preserved_contracts = (
        "validation" in semantic_source
        and "response shape" in semantic_source
        and "distinct" in semantic_source
    )
    retry_profile = (
        has_retry_delivery
        and has_completed_identity
        and has_recorded_outcome
        and has_duplicate_side_effect
        and has_preserved_contracts
    )

    has_authoritative_mutation = (
        "updates the underlying" in semantic_source
        and "role assignment" in semantic_source
    )
    has_dependent_representation = (
        "initializ" in semantic_source
        and "cach" in semantic_source
        and "stale" in semantic_source
    )
    has_dependent_reads = (
        "role-based views" in semantic_source
        and (
            "role counts" in semantic_source
            or "role_counts" in semantic_source
        )
    )
    has_consistency_repair = (
        "updated after" in semantic_source
        and (
            "re-calling" in semantic_source
            or "incremental update" in semantic_source
        )
    )
    has_preserved_state_contracts = (
        "validation" in semantic_source
        and "return values" in semantic_source
        and "public api" in semantic_source
    )
    state_consistency_profile = (
        has_authoritative_mutation
        and has_dependent_representation
        and has_dependent_reads
        and has_consistency_repair
        and has_preserved_state_contracts
    )

    if resource_profile:
        principles = [
            (
                "Bundled resource lookup should remain independent of the "
                "process working directory."
            )
        ]
        implementation_concepts = [
            (
                "Use a package-relative lookup for bundled defaults while "
                "preserving explicit caller-provided location overrides and "
                "existing output behavior."
            )
        ]
    elif retry_profile:
        principles = [
            (
                "Repeated delivery of the same logical operation should not "
                "duplicate its externally visible side effect."
            )
        ]
        implementation_concepts = [
            (
                "Associate a stable operation identity with its completed "
                "outcome; on retry, reuse that outcome before executing the "
                "side effect again."
            )
        ]
    elif state_consistency_profile:
        principles = [
            (
                "When authoritative state changes, dependent derived "
                "representations must not continue serving stale information."
            )
        ]
        implementation_concepts = [
            (
                "After an authoritative mutation, refresh or invalidate "
                "dependent derived state before subsequent reads, while "
                "preserving validation, mutation return values, and public behavior."
            )
        ]
    else:
        raise ValueError("scout handoff lacks supported compacting evidence")

    semantic_payload = {
        "compact_scout_version": "0.1",
        "source_scout_handoff_id": handoff.scout_handoff_id,
        "principles": principles,
        "implementation_concepts": implementation_concepts,
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
