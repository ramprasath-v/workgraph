import json
import shutil
from pathlib import Path

import pytest

from experience.schema import load_experience
from harness.models import AgentContext, ModelAdapter, ModelResponse
from harness.runner import run_benchmark
from recipe.schema import load_recipe
from transfer.schema import load_transfer_knowledge


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK08 = REPO_ROOT / "tasks" / "task08_catalog_updates"
TASK09 = REPO_ROOT / "tasks" / "task09_role_changes"
EXPERIENCE_PATH = (
    REPO_ROOT / "experiences" / "exp_c40ab9d4b52044919162d16cddd99d05.json"
)
RECIPE_PATH = (
    REPO_ROOT / "recipes" / "recipe_89564f793e86b9c23e0841461f1e6a60.json"
)
TRANSFER_PATH = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_6b80e8c84cf89a2f7ceec3a2278cf531.json"
)


class _FinishOnlyModel(ModelAdapter):
    name = "offline-finish-only"
    provider = "test"

    def __init__(self):
        self.contexts: list[AgentContext] = []

    def generate_action(self, context: AgentContext) -> ModelResponse:
        self.contexts.append(context)
        return ModelResponse({"action": "finish"})


def test_task08_producer_path_does_not_read_task09(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    shutil.copytree(TASK08, repo / "tasks" / "task08_catalog_updates")
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path == TASK09 or TASK09 in path.parents:
            pytest.fail("Task 09 was read during Task 08 producer execution")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    model = _FinishOnlyModel()

    result, _ = run_benchmark(
        repo,
        "task08_catalog_updates",
        model,
        max_steps=1,
    )

    assert result.task_id == "task08_catalog_updates"
    assert len(model.contexts) == 1
    context = model.contexts[0]
    assert context.prior_experience is None
    assert not hasattr(context, "analysis_contract")
    assert "task09" not in context.task_description.lower()
    assert "membership_registry.py" not in context.task_description
    assert "role_index.py" not in context.task_description


def test_verified_artifact_chain_is_linked_and_patch_free_at_transfer():
    experience = load_experience(EXPERIENCE_PATH)
    recipe = load_recipe(RECIPE_PATH)
    transfer = load_transfer_knowledge(TRANSFER_PATH)
    serialized = json.dumps(transfer.to_dict(), sort_keys=True).lower()

    assert experience.successful is True
    assert experience.verification.passed == 6
    assert experience.verification.failed == 0
    assert experience.files_changed == ["catalog.py"]
    assert recipe.source_experience_id == experience.experience_id
    assert transfer.source_recipe_id == recipe.recipe_id
    assert experience.patch.lower() not in serialized
    for forbidden in (
        "catalog.py",
        "productcatalog",
        "update_price",
        "display_price",
        "_display_prices",
        "_prices",
        "test_catalog",
        "task09",
        "membership_registry",
        "role_index",
        "member",
        "reviewer",
        "analysis_contract",
        "relevant_source_files",
        "allowed_output_files",
        "--- a/",
        "+++ b/",
        "@@ -",
    ):
        assert forbidden not in serialized


def test_transfer_contains_no_corrected_source_or_patch_lines():
    experience = load_experience(EXPERIENCE_PATH)
    transfer_text = TRANSFER_PATH.read_text(encoding="utf-8")
    pristine_source = (TASK08 / "workspace" / "catalog.py").read_text(
        encoding="utf-8"
    )
    corrected_source = pristine_source.replace(
        "        self._display_prices = {\n"
        "            product: self._format_price(cents)\n"
        "            for product, cents in self._prices.items()\n"
        "        }\n",
        "",
    ).replace(
        "        return self._display_prices[product]",
        "        return self._format_price(self._prices[product])",
    ).replace(
        "        return tuple(sorted(self._display_prices.items()))",
        "        return tuple(sorted(\n"
        "            (product, self._format_price(cents))\n"
        "            for product, cents in self._prices.items()\n"
        "        ))",
    )

    assert corrected_source != pristine_source
    assert corrected_source not in transfer_text
    for line in experience.patch.splitlines():
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            expression = line[1:].strip()
            if len(expression) >= 12:
                assert expression not in transfer_text
