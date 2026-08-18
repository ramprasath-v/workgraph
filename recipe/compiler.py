"""Deterministic compiler for the Task 02 Experience Recipe experiment."""

from __future__ import annotations

import hashlib
import json

from experience.schema import ExperienceRecord

from .schema import ExperienceRecipe, RecipeStep, RecipeVerification


def compile_recipe(experience: ExperienceRecord) -> ExperienceRecipe:
    """Compile one verified Task 02 experience without model inference."""

    if experience.task_id != "task02_config_path":
        raise ValueError("Recipe v0 only supports task02_config_path experiences")
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
