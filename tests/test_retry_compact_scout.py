import hashlib
import json
from pathlib import Path

from compact_scout.compiler import compile_compact_scout
from harness.vertex_adapter import VertexGeminiAdapter
from scout.schema import load_scout_handoff


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    REPO_ROOT
    / "scout_handoffs"
    / "scout_48f5448a867bd43b2b1fc4ae427ed5ab.json"
)
TASK06_TRANSFER = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_93a42588ddd62085a6289d9b12613079.json"
)
TASK04_SOURCE = (
    REPO_ROOT
    / "scout_handoffs"
    / "scout_78cdb2504c4636ff8b007f24762e2f9f.json"
)
TASK04_COMPACT = (
    REPO_ROOT
    / "compact_scouts"
    / "compact_scout_0f1e06290913286e9e5bb9c5ab4b1f83.json"
)


def test_retry_compilation_is_deterministic_exact_source_and_no_model_call(
    monkeypatch,
):
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == (
        "780db90755838fa70e60474b6496f7339dda5ea346178c21487d2ae0a1d63993"
    )
    handoff = load_scout_handoff(SOURCE)

    def forbidden_model_call(*args, **kwargs):
        raise AssertionError("compact compilation must not call a model")

    monkeypatch.setattr(VertexGeminiAdapter, "generate_action", forbidden_model_call)
    first = compile_compact_scout(handoff)
    second = compile_compact_scout(handoff)

    assert first == second
    assert first.source_scout_handoff_id == (
        "scout_48f5448a867bd43b2b1fc4ae427ed5ab"
    )


def test_task06_transfer_is_not_read_during_retry_compilation(monkeypatch):
    handoff = load_scout_handoff(SOURCE)
    protected = TASK06_TRANSFER.resolve()
    original_read_text = Path.read_text
    original_read_bytes = Path.read_bytes

    def guarded_read_text(path, *args, **kwargs):
        if path.resolve() == protected:
            raise AssertionError("Task 06 transfer must not be compiler input")
        return original_read_text(path, *args, **kwargs)

    def guarded_read_bytes(path, *args, **kwargs):
        if path.resolve() == protected:
            raise AssertionError("Task 06 transfer must not be compiler input")
        return original_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    compact = compile_compact_scout(handoff)
    assert compact.source_scout_handoff_id == handoff.scout_handoff_id


def test_retry_compact_guidance_is_supported_and_removes_task_details():
    handoff = load_scout_handoff(SOURCE)
    compact = compile_compact_scout(handoff)
    guidance = json.dumps(
        {
            "principles": compact.principles,
            "implementation_concepts": compact.implementation_concepts,
        },
        sort_keys=True,
    )

    assert "same logical operation" in guidance
    assert "externally visible side effect" in guidance
    assert "stable operation identity" in guidance
    assert "completed outcome" in guidance
    assert "reuse that outcome" in guidance
    for forbidden in (
        "delivery_receiver.py",
        "shipment_service.py",
        "DeliveryReceiver",
        "ShipmentService",
        "receive",
        "delivery_token",
        "order_number",
        "tracking_number",
        "test_",
        "create_shipment",
        "--- a/",
        "+++ b/",
        "@@ -",
        "```",
    ):
        assert forbidden not in guidance
    assert compact.scout_model == handoff.producer_model
    assert compact.scout_input_tokens == handoff.input_tokens
    assert compact.scout_output_tokens == handoff.output_tokens
    assert compact.scout_total_tokens == handoff.total_tokens
    assert compact.scout_elapsed_seconds == handoff.elapsed_seconds


def test_task04_compact_output_remains_byte_for_byte_unchanged(tmp_path):
    expected = TASK04_COMPACT.read_bytes()
    assert hashlib.sha256(expected).hexdigest() == (
        "4730bab5147556ac5ab3661120916077739d918dfb5ea9420b66c04cea1c1df5"
    )
    compiled = compile_compact_scout(load_scout_handoff(TASK04_SOURCE))
    output = compiled.write_json(tmp_path)

    assert output.name == TASK04_COMPACT.name
    assert output.read_bytes() == expected
