import hashlib
import json
from pathlib import Path

import pytest

from harness.ollama_adapter import OllamaModelAdapter
from harness.openai_adapter import OpenAIModelAdapter
from harness.transformers_adapter import TransformersModelAdapter
from harness.vertex_adapter import VertexGeminiAdapter
from policy.schema import (
    CompactScoutCandidate,
    HistoricalTransferCandidate,
    PolicyInput,
    TargetModelProfile,
)
from policy.v01 import decide, public_overlap, source_files_from_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_SPEC = REPO_ROOT / "policy" / "policy_v0_1.json"


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


def _input(
    *,
    tier="standard",
    languages=("python",),
    task_language="python",
    source_files=("service.py", "store.py"),
    transfer=None,
    scout=None,
):
    return PolicyInput(
        public_task_description=(
            "Update authoritative records while keeping derived views consistent."
        ),
        task_language=task_language,
        source_files=source_files,
        target_model=TargetModelProfile(
            model_identity="synthetic-model",
            capability_tier=tier,
            supported_languages=languages,
            context_window_tokens=10000,
        ),
        historical_transfer=transfer or HistoricalTransferCandidate(),
        compact_scout=scout or CompactScoutCandidate(),
    )


def _qualified_transfer(tokens=500):
    return HistoricalTransferCandidate(
        available=True,
        verified=True,
        portable_abstractions=(
            "Authoritative records and dependent derived views remain consistent.",
        ),
        estimated_context_tokens=tokens,
    )


def _qualified_scout(tokens=400):
    return CompactScoutCandidate(
        available=True,
        already_acquired=True,
        condition_permits_use=True,
        schema_valid=True,
        estimated_context_tokens=tokens,
    )


def test_same_input_always_produces_the_same_serialized_decision():
    value = _input(transfer=_qualified_transfer())

    first = decide(value).to_dict()
    second = decide(value).to_dict()

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert set(first) == {
        "policy_version", "decision", "signals", "rationale_codes"
    }


@pytest.mark.parametrize(
    ("value", "decision", "code"),
    [
        (
            _input(task_language="rust"),
            "ESCALATE",
            "TARGET_LANGUAGE_UNSUPPORTED",
        ),
        (
            _input(tier="high", transfer=_qualified_transfer()),
            "NO_ASSISTANCE",
            "HIGH_CAPABILITY_PRESERVE_UNAIDED",
        ),
        (
            _input(transfer=_qualified_transfer()),
            "HISTORICAL_TRANSFER",
            "VERIFIED_TRANSFER_HIGH_PUBLIC_OVERLAP",
        ),
        (
            _input(scout=_qualified_scout()),
            "COMPACT_CURRENT_TASK_SCOUT",
            "COMPACT_SCOUT_ALREADY_ACQUIRED",
        ),
        (
            _input(tier="low"),
            "ESCALATE",
            "LOW_CAPABILITY_WITHOUT_QUALIFIED_ASSISTANCE",
        ),
        (
            _input(source_files=tuple(f"module_{i}.py" for i in range(9))),
            "ESCALATE",
            "HIGH_STRUCTURAL_UNCERTAINTY",
        ),
        (
            _input(),
            "NO_ASSISTANCE",
            "DEFAULT_PRESERVE_UNAIDED",
        ),
    ],
)
def test_ordered_rules_cover_exactly_the_four_actions(value, decision, code):
    result = decide(value)

    assert result.decision == decision
    assert result.rationale_codes == [code]


def test_assistance_must_fit_context_budget_and_scout_must_be_permitted():
    oversized_transfer = _qualified_transfer(tokens=1501)
    unpermitted_scout = CompactScoutCandidate(
        available=True,
        already_acquired=True,
        condition_permits_use=False,
        schema_valid=True,
        estimated_context_tokens=100,
    )

    result = decide(
        _input(transfer=oversized_transfer, scout=unpermitted_scout)
    )

    assert result.decision == "NO_ASSISTANCE"
    assert result.signals["transfer_qualified"] is False
    assert result.signals["compact_scout_qualified"] is False


def test_public_similarity_is_lexical_and_deterministic():
    first = public_overlap(
        "Authoritative records update dependent views.",
        ("Dependent views follow authoritative records.",),
    )
    second = public_overlap(
        "Authoritative records update dependent views.",
        ("Dependent views follow authoritative records.",),
    )

    assert first == second == 0.8
    assert public_overlap("alpha beta", ("gamma delta",)) == 0.0


def test_workspace_profile_reads_structure_but_not_source_or_tests(tmp_path, monkeypatch):
    (tmp_path / "service.py").write_text("secret source", encoding="utf-8")
    (tmp_path / "test_service.py").write_text("hidden assertions", encoding="utf-8")
    (tmp_path / "web.ts").write_text("secret source", encoding="utf-8")
    (tmp_path / "README.md").write_text("documentation", encoding="utf-8")

    def forbidden_read(*args, **kwargs):
        raise AssertionError("workspace profiling must not read file contents")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    monkeypatch.setattr(Path, "read_bytes", forbidden_read)

    assert source_files_from_workspace(tmp_path) == ("service.py", "web.ts")


def test_policy_never_reads_benchmark_results(monkeypatch):
    original_read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        if "results" in path.parts:
            raise AssertionError("Policy v0.1 must not read benchmark results")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    assert decide(_input()).decision == "NO_ASSISTANCE"


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "hidden_evaluator_results",
        "producer_patch",
        "expected_solution",
        "current_target_history",
        "future_trajectory",
        "researcher_assistance_label",
    ],
)
def test_input_schema_rejects_forbidden_or_unknown_fields(forbidden_field):
    data = {
        "public_task_description": "A public task.",
        "task_language": "python",
        "source_files": ["service.py"],
        "target_model": {
            "model_identity": "synthetic",
            "capability_tier": "standard",
            "supported_languages": ["python"],
            "context_window_tokens": 10000,
        },
        forbidden_field: "forbidden",
    }

    with pytest.raises(ValueError, match="forbidden or unknown"):
        PolicyInput.from_dict(data)


def test_policy_contains_no_family_or_task_specific_rules():
    source = (REPO_ROOT / "policy" / "v01.py").read_text(encoding="utf-8").lower()
    specification = POLICY_SPEC.read_text(encoding="utf-8").lower()
    rendered = source + specification

    for forbidden in (
        "task01", "task02", "task03", "task04", "task05", "task06",
        "task07", "task08", "task09", "family_1", "family_2", "family_3",
        "catalog", "membership", "role_index", "retry", "idempotency",
        "current working directory", "bundled resource", "report_renderer",
    ):
        assert forbidden not in rendered


def test_policy_makes_no_model_or_provider_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Policy v0.1 must not call a model/provider")

    for adapter in (
        VertexGeminiAdapter,
        TransformersModelAdapter,
        OpenAIModelAdapter,
        OllamaModelAdapter,
    ):
        monkeypatch.setattr(adapter, "generate_action", forbidden)

    decide(_input(transfer=_qualified_transfer()))


def test_tasks_and_frozen_artifacts_remain_unchanged():
    expected = {
        "tasks": "f7ec955ff1f49289199cda21c7786c5aabefa1e6a2b61f22761db02f62bfb955",
        "experiences": "77cc9dcce5e35b3f091fe76c1d239ef465d54bc925ed177db67d33f7eec40f2c",
        "recipes": "65126b6652aff3ef87564efa601d94512cb456cd55a39d1befdeb4fbf4518eac",
        "transfer_knowledge": "57efab4d8f4dd226db3f07ee2a3fedf01494bd38bd2bc3d83402c4f89af2224f",
        "scout_handoffs": "768763b5c460f41946bd9b790be7bceaed322a9209b5036f0c53440ab9227b62",
        "compact_scouts": "4ec85c19412d83decb6ecd788b6e2a077f1a5f2bedb4afc015b6eb97ff176770",
        "results": "a8fb5853898e0f486c11c44a1f4aed64a10f94afc8023c0bd7fc0108801a50f9",
    }
    for directory, expected_hash in expected.items():
        assert _tree_hash(REPO_ROOT / directory) == expected_hash
