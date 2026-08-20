import json
from pathlib import Path

import pytest

from experience.schema import ExperienceRecord, Verification
from recipe.compiler import compile_recipe
from transfer.compiler import compile_transfer_knowledge


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK09 = REPO_ROOT / "tasks" / "task09_role_changes"


def _task08_experience() -> ExperienceRecord:
    return ExperienceRecord(
        experience_id="exp_task08_fixture",
        task_id="task08_catalog_updates",
        producer_model="verified-fixture",
        problem=(
            "Catalog views show earlier values after an accepted price update."
        ),
        environment={"language": "python"},
        files_changed=["catalog.py"],
        patch=(
            "--- a/catalog.py\n"
            "+++ b/catalog.py\n"
            "@@ -1 +1 @@\n"
            "-        self._prices[product] = cents\n"
            "+        self._prices[product] = cents; "
            "self._display_prices[product] = self._format_price(cents)\n"
        ),
        verification=Verification(
            command=["python", "-m", "pytest", "-q", "test_catalog.py"],
            passed=6,
            failed=0,
        ),
        successful=True,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        created_at="2026-01-01T00:00:01+00:00",
    )


def test_task08_recipe_and_transfer_are_deterministic_and_portable():
    experience = _task08_experience()

    first_recipe = compile_recipe(experience)
    second_recipe = compile_recipe(experience)
    first_transfer = compile_transfer_knowledge(first_recipe)
    second_transfer = compile_transfer_knowledge(second_recipe)
    serialized = json.dumps(first_transfer.to_dict(), sort_keys=True).lower()

    assert first_recipe == second_recipe
    assert first_transfer == second_transfer
    assert first_recipe.task_type == "derived_state_consistency"
    assert "authoritative state" in serialized
    assert "dependent derived" in serialized
    assert "stale information" in serialized
    assert experience.patch.lower() not in serialized
    for forbidden in (
        "catalog.py",
        "productcatalog",
        "update_price",
        "display_price",
        "_display_prices",
        "notebook",
        "membership_registry",
        "role_index",
        "member",
        "reviewer",
        "analysis_contract",
        "--- a/",
        "+++ b/",
        "@@ -",
        "test_catalog",
    ):
        assert forbidden not in serialized


def test_task08_compilation_does_not_read_task09(monkeypatch):
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path == TASK09 or TASK09 in path.parents:
            pytest.fail("Task 09 was read during Task 08 compilation")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    recipe = compile_recipe(_task08_experience())
    transfer = compile_transfer_knowledge(recipe)

    assert transfer.source_recipe_id == recipe.recipe_id


def test_task08_compilation_requires_verified_dependent_state_evidence():
    experience = _task08_experience()
    incomplete = ExperienceRecord(
        **{
            **experience.__dict__,
            "patch": "--- a/catalog.py\n+++ b/catalog.py\n",
        }
    )

    with pytest.raises(ValueError, match="dependent-state evidence"):
        compile_recipe(incomplete)
