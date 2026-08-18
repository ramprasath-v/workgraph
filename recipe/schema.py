"""Minimal JSON schema for Experience Recipe v0."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RecipeStep:
    step: int
    instruction: str


@dataclass(frozen=True)
class RecipeVerification:
    previously_passed: int
    previously_failed: int


@dataclass(frozen=True)
class ExperienceRecipe:
    recipe_version: str
    recipe_id: str
    source_experience_id: str
    task_id: str
    task_type: str
    problem: str
    target_files: list[str]
    steps: list[RecipeStep]
    verification: RecipeVerification
    implementation_concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "ExperienceRecipe":
        if not isinstance(data, dict):
            raise ValueError("recipe must be a JSON object")
        string_fields = (
            "recipe_version",
            "recipe_id",
            "source_experience_id",
            "task_id",
            "task_type",
            "problem",
        )
        if any(not isinstance(data.get(field), str) for field in string_fields):
            raise ValueError("recipe has a missing or invalid string field")
        if data["recipe_version"] not in {"0.1", "0.2"}:
            raise ValueError("unsupported recipe version")
        targets = data.get("target_files")
        if not isinstance(targets, list) or not targets or not all(
            isinstance(path, str) and path for path in targets
        ):
            raise ValueError("recipe target_files must be non-empty strings")
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("recipe steps must be a non-empty list")
        steps: list[RecipeStep] = []
        for expected_step, raw_step in enumerate(raw_steps, start=1):
            if not isinstance(raw_step, dict):
                raise ValueError("recipe step must be an object")
            step = raw_step.get("step")
            instruction = raw_step.get("instruction")
            if step != expected_step or not isinstance(instruction, str) or not instruction:
                raise ValueError("recipe steps must be sequential and non-empty")
            steps.append(RecipeStep(step, instruction))
        verification = data.get("verification")
        if not isinstance(verification, dict):
            raise ValueError("recipe verification must be an object")
        passed = verification.get("previously_passed")
        failed = verification.get("previously_failed")
        if (
            not isinstance(passed, int)
            or isinstance(passed, bool)
            or passed < 0
            or not isinstance(failed, int)
            or isinstance(failed, bool)
            or failed < 0
        ):
            raise ValueError("recipe verification counts are invalid")
        concepts = data.get("implementation_concepts", [])
        if not isinstance(concepts, list) or not all(
            isinstance(concept, str) and concept for concept in concepts
        ):
            raise ValueError(
                "recipe implementation_concepts must be a list of strings"
            )
        return cls(
            recipe_version=data["recipe_version"],
            recipe_id=data["recipe_id"],
            source_experience_id=data["source_experience_id"],
            task_id=data["task_id"],
            task_type=data["task_type"],
            problem=data["problem"],
            target_files=list(targets),
            steps=steps,
            verification=RecipeVerification(passed, failed),
            implementation_concepts=list(concepts),
        )

    def write_json(self, recipes_dir: Path) -> Path:
        recipes_dir.mkdir(parents=True, exist_ok=True)
        destination = recipes_dir / f"{self.recipe_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination


def load_recipe(path: Path) -> ExperienceRecipe:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"recipe file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load recipe {path}: {exc}") from exc
    return ExperienceRecipe.from_dict(data)
