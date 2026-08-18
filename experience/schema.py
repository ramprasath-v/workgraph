"""Minimal serializable schema for a successful coding experience."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Verification:
    command: list[str]
    passed: int
    failed: int


@dataclass(frozen=True)
class ExperienceRecord:
    experience_id: str
    task_id: str
    producer_model: str
    problem: str
    environment: dict[str, str]
    files_changed: list[str]
    patch: str
    verification: Verification
    successful: bool
    started_at: str
    completed_at: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "ExperienceRecord":
        if not isinstance(data, dict):
            raise ValueError("experience must be a JSON object")
        required_strings = (
            "experience_id",
            "task_id",
            "producer_model",
            "problem",
            "patch",
            "started_at",
            "completed_at",
            "created_at",
        )
        if any(not isinstance(data.get(field), str) for field in required_strings):
            raise ValueError("experience has a missing or invalid string field")
        environment = data.get("environment")
        files_changed = data.get("files_changed")
        verification = data.get("verification")
        if not isinstance(environment, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in environment.items()
        ):
            raise ValueError("experience environment must map strings to strings")
        if not isinstance(files_changed, list) or not all(
            isinstance(path, str) for path in files_changed
        ):
            raise ValueError("experience files_changed must be a list of strings")
        if not isinstance(verification, dict):
            raise ValueError("experience verification must be an object")
        command = verification.get("command")
        passed = verification.get("passed")
        failed = verification.get("failed")
        if not isinstance(command, list) or not all(
            isinstance(part, str) for part in command
        ):
            raise ValueError("experience verification command is invalid")
        if not isinstance(passed, int) or not isinstance(failed, int):
            raise ValueError("experience verification counts are invalid")
        if data.get("successful") is not True:
            raise ValueError("only successful experiences can be consumed")
        return cls(
            experience_id=data["experience_id"],
            task_id=data["task_id"],
            producer_model=data["producer_model"],
            problem=data["problem"],
            environment=dict(environment),
            files_changed=list(files_changed),
            patch=data["patch"],
            verification=Verification(
                command=list(command), passed=passed, failed=failed
            ),
            successful=True,
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            created_at=data["created_at"],
        )

    def write_json(self, experiences_dir: Path) -> Path:
        experiences_dir.mkdir(parents=True, exist_ok=True)
        destination = experiences_dir / f"{self.experience_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def load_experience(path: Path) -> ExperienceRecord:
    """Load and validate one explicitly selected successful experience JSON."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"experience file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load experience {path}: {exc}") from exc
    return ExperienceRecord.from_dict(data)
