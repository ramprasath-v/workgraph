"""Serializable provenance-preserving compact scout schema."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompactScoutKnowledge:
    compact_scout_version: str
    compact_scout_id: str
    source_scout_handoff_id: str
    principles: list[str]
    implementation_concepts: list[str]
    scout_provider: str
    scout_model: str
    scout_input_tokens: int
    scout_output_tokens: int
    scout_total_tokens: int
    scout_elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "CompactScoutKnowledge":
        if not isinstance(data, dict):
            raise ValueError("compact scout must be a JSON object")
        strings = (
            "compact_scout_version",
            "compact_scout_id",
            "source_scout_handoff_id",
            "scout_provider",
            "scout_model",
        )
        if any(not isinstance(data.get(name), str) or not data[name] for name in strings):
            raise ValueError("compact scout has a missing or invalid string field")
        if data["compact_scout_version"] != "0.1":
            raise ValueError("unsupported compact scout version")
        collections: dict[str, list[str]] = {}
        for name in ("principles", "implementation_concepts"):
            values = data.get(name)
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str)
                and value.strip()
                and "\n" not in value
                and len(value) <= 400
                for value in values
            ):
                raise ValueError(f"compact scout {name} must be concise strings")
            collections[name] = list(values)
        integer_fields = (
            "scout_input_tokens",
            "scout_output_tokens",
            "scout_total_tokens",
        )
        if any(
            not isinstance(data.get(name), int)
            or isinstance(data[name], bool)
            or data[name] < 0
            for name in integer_fields
        ):
            raise ValueError("compact scout token counts must be non-negative")
        elapsed = data.get("scout_elapsed_seconds")
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
            raise ValueError("compact scout elapsed time must be non-negative")
        guidance = json.dumps(collections, sort_keys=True)
        for forbidden in ("--- a/", "+++ b/", "@@ -", "```"):
            if forbidden in guidance:
                raise ValueError("compact scout must not contain patches or code blocks")
        return cls(
            compact_scout_version=data["compact_scout_version"],
            compact_scout_id=data["compact_scout_id"],
            source_scout_handoff_id=data["source_scout_handoff_id"],
            principles=collections["principles"],
            implementation_concepts=collections["implementation_concepts"],
            scout_provider=data["scout_provider"],
            scout_model=data["scout_model"],
            scout_input_tokens=data["scout_input_tokens"],
            scout_output_tokens=data["scout_output_tokens"],
            scout_total_tokens=data["scout_total_tokens"],
            scout_elapsed_seconds=float(elapsed),
        )

    def write_json(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"{self.compact_scout_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def load_compact_scout(path: Path) -> CompactScoutKnowledge:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"compact scout file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load compact scout {path}: {exc}") from exc
    return CompactScoutKnowledge.from_dict(data)
