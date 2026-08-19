"""Minimal serializable schema for a current-task scout handoff."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


def _short_lines(data: object, name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(data, list) or (not data and not allow_empty):
        raise ValueError(f"scout handoff {name} must be a non-empty list")
    if not all(
        isinstance(value, str)
        and value.strip()
        and "\n" not in value
        and len(value) <= 400
        for value in data
    ):
        raise ValueError(f"scout handoff {name} must contain concise single lines")
    return list(data)


@dataclass(frozen=True)
class ScoutHandoff:
    scout_handoff_version: str
    scout_handoff_id: str
    task_id: str
    producer_provider: str
    producer_model: str
    observations: list[str]
    suspected_area: str
    recommended_investigation: list[str]
    constraints: list[str]
    files_inspected: list[str]
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_seconds: float
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "ScoutHandoff":
        if not isinstance(data, dict):
            raise ValueError("scout handoff must be a JSON object")
        strings = (
            "scout_handoff_version",
            "scout_handoff_id",
            "task_id",
            "producer_provider",
            "producer_model",
            "suspected_area",
            "created_at",
        )
        if any(not isinstance(data.get(name), str) or not data[name] for name in strings):
            raise ValueError("scout handoff has a missing or invalid string field")
        if data["scout_handoff_version"] != "0.1":
            raise ValueError("unsupported scout handoff version")
        suspected_area = data["suspected_area"]
        if "\n" in suspected_area or len(suspected_area) > 400:
            raise ValueError("scout handoff suspected_area must be concise")
        observations = _short_lines(data.get("observations"), "observations")
        investigation = _short_lines(
            data.get("recommended_investigation"), "recommended_investigation"
        )
        constraints = _short_lines(data.get("constraints"), "constraints")
        files = _short_lines(
            data.get("files_inspected"), "files_inspected", allow_empty=True
        )
        integer_fields = ("tool_calls", "input_tokens", "output_tokens", "total_tokens")
        if any(
            not isinstance(data.get(name), int)
            or isinstance(data[name], bool)
            or data[name] < 0
            for name in integer_fields
        ):
            raise ValueError("scout handoff counters must be non-negative integers")
        elapsed = data.get("elapsed_seconds")
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
            raise ValueError("scout handoff elapsed_seconds must be non-negative")
        serialized_analysis = json.dumps(
            {
                "observations": observations,
                "suspected_area": suspected_area,
                "recommended_investigation": investigation,
                "constraints": constraints,
            },
            sort_keys=True,
        )
        for forbidden in ("--- a/", "+++ b/", "@@ -", "```"):
            if forbidden in serialized_analysis:
                raise ValueError("scout handoff must not contain patches or code blocks")
        return cls(
            scout_handoff_version=data["scout_handoff_version"],
            scout_handoff_id=data["scout_handoff_id"],
            task_id=data["task_id"],
            producer_provider=data["producer_provider"],
            producer_model=data["producer_model"],
            observations=observations,
            suspected_area=suspected_area,
            recommended_investigation=investigation,
            constraints=constraints,
            files_inspected=files,
            tool_calls=data["tool_calls"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            total_tokens=data["total_tokens"],
            elapsed_seconds=float(elapsed),
            created_at=data["created_at"],
        )

    @classmethod
    def create(cls, **data: object) -> "ScoutHandoff":
        semantic = dict(data)
        canonical = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
        semantic["scout_handoff_id"] = (
            f"scout_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]}"
        )
        semantic["scout_handoff_version"] = "0.1"
        return cls.from_dict(semantic)

    def write_json(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"{self.scout_handoff_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def load_scout_handoff(path: Path) -> ScoutHandoff:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"scout handoff file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load scout handoff {path}: {exc}") from exc
    return ScoutHandoff.from_dict(data)
