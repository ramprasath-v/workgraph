"""Typed input and output schema for assistance-selection Policy v0.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DECISIONS = frozenset(
    {
        "NO_ASSISTANCE",
        "HISTORICAL_TRANSFER",
        "COMPACT_CURRENT_TASK_SCOUT",
        "ESCALATE",
    }
)
CAPABILITY_TIERS = frozenset({"low", "standard", "high"})


def _non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_tuple(value: object, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or (
        not value and not allow_empty
    ) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
    return tuple(value)


def _non_negative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class TargetModelProfile:
    model_identity: str
    capability_tier: str
    supported_languages: tuple[str, ...]
    context_window_tokens: int

    def __post_init__(self) -> None:
        _non_empty_string(self.model_identity, "model_identity")
        if self.capability_tier not in CAPABILITY_TIERS:
            raise ValueError("capability_tier must be low, standard, or high")
        _string_tuple(self.supported_languages, "supported_languages")
        _positive_int(self.context_window_tokens, "context_window_tokens")


@dataclass(frozen=True)
class HistoricalTransferCandidate:
    available: bool = False
    verified: bool = False
    portable_abstractions: tuple[str, ...] = ()
    estimated_context_tokens: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.available, bool) or not isinstance(self.verified, bool):
            raise ValueError("transfer availability and verification must be booleans")
        _string_tuple(
            self.portable_abstractions,
            "portable_abstractions",
            allow_empty=not self.available,
        )
        _non_negative_int(
            self.estimated_context_tokens, "transfer estimated_context_tokens"
        )


@dataclass(frozen=True)
class CompactScoutCandidate:
    available: bool = False
    already_acquired: bool = False
    condition_permits_use: bool = False
    schema_valid: bool = False
    estimated_context_tokens: int = 0

    def __post_init__(self) -> None:
        for name in (
            "available",
            "already_acquired",
            "condition_permits_use",
            "schema_valid",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"compact scout {name} must be boolean")
        _non_negative_int(
            self.estimated_context_tokens, "scout estimated_context_tokens"
        )


@dataclass(frozen=True)
class PolicyInput:
    public_task_description: str
    task_language: str
    source_files: tuple[str, ...]
    target_model: TargetModelProfile
    historical_transfer: HistoricalTransferCandidate = HistoricalTransferCandidate()
    compact_scout: CompactScoutCandidate = CompactScoutCandidate()

    def __post_init__(self) -> None:
        _non_empty_string(self.public_task_description, "public_task_description")
        _non_empty_string(self.task_language, "task_language")
        _string_tuple(self.source_files, "source_files", allow_empty=True)
        if len(set(self.source_files)) != len(self.source_files):
            raise ValueError("source_files must be unique")
        if any(path.startswith("/") or ".." in path.split("/") for path in self.source_files):
            raise ValueError("source_files must be workspace-relative paths")

    @classmethod
    def from_dict(cls, data: object) -> "PolicyInput":
        if not isinstance(data, dict):
            raise ValueError("policy input must be an object")
        allowed = {
            "public_task_description",
            "task_language",
            "source_files",
            "target_model",
            "historical_transfer",
            "compact_scout",
        }
        if set(data) - allowed:
            raise ValueError("policy input contains forbidden or unknown fields")
        target = data.get("target_model")
        transfer = data.get("historical_transfer", {})
        scout = data.get("compact_scout", {})
        if not all(isinstance(value, dict) for value in (target, transfer, scout)):
            raise ValueError("policy input profiles must be objects")
        target_allowed = {
            "model_identity",
            "capability_tier",
            "supported_languages",
            "context_window_tokens",
        }
        transfer_allowed = {
            "available",
            "verified",
            "portable_abstractions",
            "estimated_context_tokens",
        }
        scout_allowed = {
            "available",
            "already_acquired",
            "condition_permits_use",
            "schema_valid",
            "estimated_context_tokens",
        }
        if set(target) - target_allowed or set(transfer) - transfer_allowed or set(scout) - scout_allowed:
            raise ValueError("policy profile contains forbidden or unknown fields")
        return cls(
            public_task_description=_non_empty_string(
                data.get("public_task_description"), "public_task_description"
            ),
            task_language=_non_empty_string(data.get("task_language"), "task_language"),
            source_files=_string_tuple(
                data.get("source_files"), "source_files", allow_empty=True
            ),
            target_model=TargetModelProfile(
                model_identity=_non_empty_string(
                    target.get("model_identity"), "model_identity"
                ),
                capability_tier=_non_empty_string(
                    target.get("capability_tier"), "capability_tier"
                ),
                supported_languages=_string_tuple(
                    target.get("supported_languages"), "supported_languages"
                ),
                context_window_tokens=target.get("context_window_tokens"),
            ),
            historical_transfer=HistoricalTransferCandidate(
                available=transfer.get("available", False),
                verified=transfer.get("verified", False),
                portable_abstractions=_string_tuple(
                    transfer.get("portable_abstractions", ()),
                    "portable_abstractions",
                    allow_empty=not transfer.get("available", False),
                ),
                estimated_context_tokens=transfer.get("estimated_context_tokens", 0),
            ),
            compact_scout=CompactScoutCandidate(
                available=scout.get("available", False),
                already_acquired=scout.get("already_acquired", False),
                condition_permits_use=scout.get("condition_permits_use", False),
                schema_valid=scout.get("schema_valid", False),
                estimated_context_tokens=scout.get("estimated_context_tokens", 0),
            ),
        )


@dataclass(frozen=True)
class PolicyDecision:
    policy_version: str
    decision: str
    signals: dict[str, Any]
    rationale_codes: list[str]

    def __post_init__(self) -> None:
        if self.policy_version != "0.1":
            raise ValueError("unsupported policy version")
        if self.decision not in DECISIONS:
            raise ValueError("invalid policy decision")
        if not isinstance(self.signals, dict):
            raise ValueError("policy signals must be an object")
        if not self.rationale_codes or not all(
            isinstance(code, str) and code for code in self.rationale_codes
        ):
            raise ValueError("rationale_codes must be non-empty strings")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
