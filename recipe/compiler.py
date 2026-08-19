"""Deterministic compiler for supported verified experience recipes."""

from __future__ import annotations

import hashlib
import json

from experience.schema import ExperienceRecord

from .schema import ExperienceRecipe, RecipeStep, RecipeVerification


def compile_recipe(experience: ExperienceRecord) -> ExperienceRecipe:
    """Compile one supported verified experience without model inference."""

    if experience.task_id == "task05_identifier_normalization":
        return _compile_identifier_normalization_recipe(experience)

    if experience.task_id != "task02_config_path":
        raise ValueError("unsupported experience task for Recipe v0")
    if "app.py" not in experience.files_changed:
        raise ValueError("Task 02 recipe requires app.py in files_changed")
    patch = experience.patch
    if "config/settings.json" not in patch or "__file__" not in patch:
        raise ValueError("Task 02 experience patch lacks the expected path evidence")

    semantic_payload = {
        "recipe_version": "0.2",
        "source_experience_id": experience.experience_id,
        "task_id": experience.task_id,
        "task_type": "config_path_fix",
        "problem": (
            "Default configuration loading depends on the process working "
            "directory."
        ),
        "target_files": list(experience.files_changed),
        "steps": [
            "Inspect app.py and locate the default configuration-path logic.",
            "Preserve caller-supplied config_path behavior.",
            (
                "When config_path is not supplied, resolve "
                "config/settings.json relative to the directory containing "
                "app.py rather than the process working directory."
            ),
            "Run the task test suite after modifying app.py.",
        ],
        "implementation_concepts": [
            (
                "For a path relative to the Python module rather than the "
                "current working directory, use __file__ as the path anchor."
            )
        ],
        "verification": {
            "previously_passed": experience.verification.passed,
            "previously_failed": experience.verification.failed,
        },
    }
    canonical = json.dumps(
        semantic_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    recipe_id = f"recipe_{hashlib.sha256(canonical).hexdigest()[:32]}"
    return ExperienceRecipe(
        recipe_version="0.2",
        recipe_id=recipe_id,
        source_experience_id=experience.experience_id,
        task_id=experience.task_id,
        task_type="config_path_fix",
        problem=semantic_payload["problem"],
        target_files=list(experience.files_changed),
        steps=[
            RecipeStep(index, instruction)
            for index, instruction in enumerate(semantic_payload["steps"], start=1)
        ],
        verification=RecipeVerification(
            experience.verification.passed,
            experience.verification.failed,
        ),
        implementation_concepts=list(
            semantic_payload["implementation_concepts"]
        ),
    )


def _compile_identifier_normalization_recipe(
    experience: ExperienceRecord,
) -> ExperienceRecipe:
    if "user_registry.py" not in experience.files_changed:
        raise ValueError("Task 05 recipe requires user_registry.py in files_changed")
    patch = experience.patch
    if ".strip()" not in patch or not any(
        marker in patch for marker in (".casefold()", ".lower()")
    ):
        raise ValueError(
            "Task 05 experience patch lacks verified normalization evidence"
        )

    semantic_payload = {
        "recipe_version": "0.2",
        "source_experience_id": experience.experience_id,
        "task_id": experience.task_id,
        "task_type": "identifier_normalization",
        "problem": (
            "Equivalent externally supplied textual identifiers are treated "
            "as different logical users."
        ),
        "target_files": list(experience.files_changed),
        "steps": [
            "Inspect the identifier registration and lookup behavior.",
            "Preserve the existing invalid-identifier validation contract.",
            (
                "Normalize surrounding whitespace and letter casing "
                "consistently before identifier comparison or persistence."
            ),
            "Run the task test suite after modifying the implementation.",
        ],
        "implementation_concepts": [
            (
                "Apply identifier normalization at the input boundary while "
                "preserving existing validation behavior."
            )
        ],
        "verification": {
            "previously_passed": experience.verification.passed,
            "previously_failed": experience.verification.failed,
        },
    }
    canonical = json.dumps(
        semantic_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    recipe_id = f"recipe_{hashlib.sha256(canonical).hexdigest()[:32]}"
    return ExperienceRecipe(
        recipe_version="0.2",
        recipe_id=recipe_id,
        source_experience_id=experience.experience_id,
        task_id=experience.task_id,
        task_type=semantic_payload["task_type"],
        problem=semantic_payload["problem"],
        target_files=list(experience.files_changed),
        steps=[
            RecipeStep(index, instruction)
            for index, instruction in enumerate(semantic_payload["steps"], start=1)
        ],
        verification=RecipeVerification(
            experience.verification.passed,
            experience.verification.failed,
        ),
        implementation_concepts=list(
            semantic_payload["implementation_concepts"]
        ),
    )
