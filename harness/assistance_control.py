"""Deterministic assistance-control payloads for prompt ablations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .verification_integrity import validate_protected_files


WRAPPER_TEMPLATE_ID = "optional-context-v1"


def payload_sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approximate_tokens(payload: str) -> int:
    """Deterministic chars/4 approximation, rounded upward."""

    return (len(payload) + 3) // 4


@dataclass(frozen=True)
class AssistanceControl:
    assistance_control_version: str
    assistance_control_id: str
    condition_id: str
    wrapper_template_id: str
    payload: str
    payload_sha256: str
    payload_character_count: int
    payload_approximate_tokens: int
    protected_evaluator_files: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.assistance_control_version != "0.1":
            raise ValueError("unsupported assistance control version")
        if self.wrapper_template_id != WRAPPER_TEMPLATE_ID:
            raise ValueError("unsupported assistance wrapper template")
        if not self.assistance_control_id or not self.condition_id:
            raise ValueError("assistance control identifiers are required")
        if not isinstance(self.payload, str) or not self.payload:
            raise ValueError("assistance payload must be non-empty text")
        if self.payload_sha256 != payload_sha256(self.payload):
            raise ValueError("assistance payload hash mismatch")
        if self.payload_character_count != len(self.payload):
            raise ValueError("assistance payload character count mismatch")
        if self.payload_approximate_tokens != approximate_tokens(self.payload):
            raise ValueError("assistance payload token approximation mismatch")
        object.__setattr__(
            self,
            "protected_evaluator_files",
            validate_protected_files(self.protected_evaluator_files),
        )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["protected_evaluator_files"] = list(self.protected_evaluator_files)
        return value


def load_assistance_control(path: Path) -> AssistanceControl:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load assistance control {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("assistance control must be a JSON object")
    expected = {
        "assistance_control_version", "assistance_control_id", "condition_id",
        "wrapper_template_id", "payload", "payload_sha256",
        "payload_character_count", "payload_approximate_tokens",
        "protected_evaluator_files",
    }
    if set(value) != expected:
        raise ValueError("assistance control fields do not match schema")
    protected = value["protected_evaluator_files"]
    if not isinstance(protected, list):
        raise ValueError("protected_evaluator_files must be a list")
    return AssistanceControl(
        **{**value, "protected_evaluator_files": tuple(protected)}
    )
