"""Minimal serializable schema for cross-task transfer knowledge."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TransferKnowledge:
    transfer_version: str
    transfer_knowledge_id: str
    source_recipe_id: str
    principles: list[str]
    implementation_concepts: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "TransferKnowledge":
        if not isinstance(data, dict):
            raise ValueError("transfer knowledge must be a JSON object")
        string_fields = (
            "transfer_version",
            "transfer_knowledge_id",
            "source_recipe_id",
        )
        if any(not isinstance(data.get(field), str) for field in string_fields):
            raise ValueError(
                "transfer knowledge has a missing or invalid string field"
            )
        if data["transfer_version"] != "0.1":
            raise ValueError("unsupported transfer knowledge version")
        principles = data.get("principles")
        concepts = data.get("implementation_concepts")
        for name, values in (
            ("principles", principles),
            ("implementation_concepts", concepts),
        ):
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value for value in values
            ):
                raise ValueError(
                    f"transfer knowledge {name} must be non-empty strings"
                )
        return cls(
            transfer_version=data["transfer_version"],
            transfer_knowledge_id=data["transfer_knowledge_id"],
            source_recipe_id=data["source_recipe_id"],
            principles=list(principles),
            implementation_concepts=list(concepts),
        )

    def write_json(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"{self.transfer_knowledge_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def load_transfer_knowledge(path: Path) -> TransferKnowledge:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"transfer knowledge file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load transfer knowledge {path}: {exc}") from exc
    return TransferKnowledge.from_dict(data)
