"""Deterministically retain only portable knowledge from a recipe."""

from __future__ import annotations

import hashlib
import json

from recipe.schema import ExperienceRecipe

from .schema import TransferKnowledge


def compile_transfer_knowledge(recipe: ExperienceRecipe) -> TransferKnowledge:
    if not recipe.implementation_concepts:
        raise ValueError("source recipe has no implementation concepts to transfer")
    semantic_payload = {
        "transfer_version": "0.1",
        "source_recipe_id": recipe.recipe_id,
        "principles": [
            (
                "Relative resource paths can fail when the process working "
                "directory changes."
            )
        ],
        "implementation_concepts": list(recipe.implementation_concepts),
    }
    canonical = json.dumps(
        semantic_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    transfer_id = f"transfer_{hashlib.sha256(canonical).hexdigest()[:32]}"
    return TransferKnowledge(
        transfer_version="0.1",
        transfer_knowledge_id=transfer_id,
        source_recipe_id=recipe.recipe_id,
        principles=list(semantic_payload["principles"]),
        implementation_concepts=list(
            semantic_payload["implementation_concepts"]
        ),
    )
