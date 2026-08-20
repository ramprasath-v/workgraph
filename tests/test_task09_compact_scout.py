import hashlib
import json
from pathlib import Path

import pytest

from compact_scout.compiler import compile_compact_scout
from compact_scout.schema import load_compact_scout
from harness.vertex_adapter import VertexGeminiAdapter
from scout.schema import load_scout_handoff


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    REPO_ROOT
    / "scout_handoffs"
    / "scout_ed6739707d4474f82577cd4d5da3c82b.json"
)
COMPACT = (
    REPO_ROOT
    / "compact_scouts"
    / "compact_scout_2dafc6a6e899b8423c3c76376f9a0dfb.json"
)
EXISTING_COMPACT_HASHES = {
    "compact_scout_0f1e06290913286e9e5bb9c5ab4b1f83.json": (
        "4730bab5147556ac5ab3661120916077739d918dfb5ea9420b66c04cea1c1df5"
    ),
    "compact_scout_bb485114b03cac9c87e66be0fb9193f9.json": (
        "f2721a211d1b5a4ca211617771b39a1a50900b1ef314f4712f15e46e27f7fd7e"
    ),
}


def test_task09_compilation_is_deterministic_and_model_free(monkeypatch):
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert source_hash == (
        "ec38b8443bcc5eaaec4ef8b71c673b29e10a9280d68fe8a01f2967c245869791"
    )
    handoff = load_scout_handoff(SOURCE)

    def forbidden_model_call(*args, **kwargs):
        raise AssertionError("compact compilation must not call a model")

    monkeypatch.setattr(VertexGeminiAdapter, "generate_action", forbidden_model_call)
    first = compile_compact_scout(handoff)
    second = compile_compact_scout(handoff)

    assert first == second
    assert first.source_scout_handoff_id == handoff.scout_handoff_id
    assert first.scout_provider == handoff.producer_provider
    assert first.scout_model == handoff.producer_model
    assert first.scout_input_tokens == handoff.input_tokens
    assert first.scout_output_tokens == handoff.output_tokens
    assert first.scout_total_tokens == handoff.total_tokens
    assert first.scout_elapsed_seconds == handoff.elapsed_seconds
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash


def test_task09_compact_guidance_is_generic_and_leak_free():
    compact = compile_compact_scout(load_scout_handoff(SOURCE))
    guidance = json.dumps(
        {
            "principles": compact.principles,
            "implementation_concepts": compact.implementation_concepts,
        },
        sort_keys=True,
    ).lower()

    assert "authoritative state" in guidance
    assert "dependent derived" in guidance
    assert "stale information" in guidance
    assert "refresh or invalidate" in guidance
    for forbidden in (
        "task09",
        "membership_registry.py",
        "role_index.py",
        "test_role_index.py",
        "membershipregistry",
        "roleindex",
        "change_role",
        "members_with_role",
        "role_counts",
        "_members_by_role",
        "_build_index",
        "ari",
        "reviewer",
        "assert ",
        "pytest",
        "analysis_contract",
        "relevant_source_files",
        "allowed_output_files",
        "qwen",
        "baseline",
        "transfer_",
        "--- a/",
        "+++ b/",
        "@@ -",
        "```",
    ):
        assert forbidden not in guidance


def test_incomplete_state_consistency_evidence_is_rejected():
    handoff = load_scout_handoff(SOURCE)
    data = handoff.to_dict()
    data["observations"] = ["A stale value was observed."]
    data["suspected_area"] = "A value may require investigation."
    data["recommended_investigation"] = ["Inspect later reads."]
    data["constraints"] = ["Preserve public behavior."]

    with pytest.raises(ValueError, match="lacks supported compacting evidence"):
        compile_compact_scout(type(handoff).from_dict(data))


def test_existing_compact_scouts_remain_byte_identical():
    for filename, expected_hash in EXISTING_COMPACT_HASHES.items():
        path = REPO_ROOT / "compact_scouts" / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash


def test_generated_task09_compact_matches_deterministic_compilation():
    generated = load_compact_scout(COMPACT)
    compiled = compile_compact_scout(load_scout_handoff(SOURCE))

    assert generated == compiled
    assert generated.compact_scout_id == (
        "compact_scout_2dafc6a6e899b8423c3c76376f9a0dfb"
    )
    assert generated.source_scout_handoff_id == (
        "scout_ed6739707d4474f82577cd4d5da3c82b"
    )
    assert hashlib.sha256(COMPACT.read_bytes()).hexdigest() == (
        "b9125dd832e4caed5589d3c90fcbc8a987c12b3ca23081ab5aa915ffe1f00c2c"
    )
