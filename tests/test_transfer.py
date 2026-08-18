import json
import shutil
from pathlib import Path

from harness.models import AgentContext, MockModelAdapter
from harness.prompting import build_model_prompt, format_transfer_knowledge
from harness.runner import run_repeated_benchmark
from recipe.schema import load_recipe
from transfer.compiler import compile_transfer_knowledge
from transfer.schema import load_transfer_knowledge


REPO_ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = (
    REPO_ROOT
    / "recipes"
    / "recipe_98832e7c414d8cb42300e4dbc80d7535.json"
)
EXPERIENCE_PATH = (
    REPO_ROOT
    / "experiences"
    / "exp_aedf873f3b13471ea3e0145e4a4c7c2d.json"
)
TRANSFER_PATH = (
    REPO_ROOT
    / "transfer_knowledge"
    / "transfer_a4142b399f8684e6a75fda4a625ed4d8.json"
)


def test_transfer_compilation_is_deterministic_and_serializable(tmp_path: Path):
    recipe = load_recipe(RECIPE_PATH)

    first = compile_transfer_knowledge(recipe)
    second = compile_transfer_knowledge(recipe)
    output = first.write_json(tmp_path / "transfer_knowledge")

    assert first == second
    assert first.transfer_knowledge_id == second.transfer_knowledge_id
    assert load_transfer_knowledge(output) == first
    assert first.source_recipe_id == recipe.recipe_id


def test_transfer_artifact_contains_only_portable_knowledge():
    recipe = load_recipe(RECIPE_PATH)
    transfer = compile_transfer_knowledge(recipe)
    serialized = json.dumps(transfer.to_dict(), sort_keys=True)
    raw_patch = json.loads(EXPERIENCE_PATH.read_text(encoding="utf-8"))["patch"]

    assert "__file__" in serialized
    assert "working directory" in serialized
    assert raw_patch not in serialized
    for forbidden in (
        "app.py",
        "config/settings.json",
        "load_settings",
        "config_path",
        "task02_config_path",
        "4 passed",
    ):
        assert forbidden not in serialized


def test_transfer_prompt_warns_that_source_task_differs_without_target_hint():
    transfer = compile_transfer_knowledge(load_recipe(RECIPE_PATH))
    rendered = format_transfer_knowledge(transfer.to_dict())
    context = AgentContext(
        task_id="task03_resource_path",
        task_description=(
            "Bundled template loading fails from different working directories."
        ),
        available_tools=("list_files", "read_file", "write_file", "run_tests"),
        prior_experience=transfer.to_dict(),
    )
    prompt = build_model_prompt(context)

    assert "PRIOR VERIFIED TRANSFER KNOWLEDGE" in rendered
    assert "This came from a different task." in rendered
    assert (
        "Do not assume filenames, paths, functions, or project structure are "
        "the same." in rendered
    )
    assert (
        "Concepts such as __file__ describe implementation mechanisms" in rendered
    )
    assert "do not treat them as filenames or workspace paths to inspect" in rendered
    assert "No current-workspace file has been successfully inspected yet." in rendered
    assert "Discovering the workspace structure" in rendered
    assert "Choose ONLY the next single tool action." in rendered
    assert "__file__" in rendered
    assert "template_loader.py" not in rendered
    assert "assets/template.json" not in rendered
    assert "app.py" not in rendered
    assert "PRIOR VERIFIED TRANSFER KNOWLEDGE" in prompt
    assert "PRIOR VERIFIED EXPERIENCE\n--- BEGIN" not in prompt


def test_transfer_prompt_switches_grounding_after_successful_file_read():
    transfer = compile_transfer_knowledge(load_recipe(RECIPE_PATH))
    history = (
        {
            "action": {"action": "read_file", "path": "discovered_source.py"},
            "output": "CURRENT_WORKSPACE_SOURCE_CONTENT",
        },
    )

    rendered = format_transfer_knowledge(
        transfer.to_dict(), history=history
    )

    assert "A current-workspace file has already been successfully inspected." in rendered
    assert "Use the current workspace contents and the transferred principle" in rendered
    assert "do not treat them as filenames or workspace paths to inspect" in rendered
    assert "No current-workspace file has been successfully inspected yet." not in rendered
    assert "Discovering the workspace structure" not in rendered
    assert "discovered_source.py" not in rendered
    assert "CURRENT_WORKSPACE_SOURCE_CONTENT" not in rendered


def test_failed_file_read_does_not_advance_transfer_grounding():
    transfer = compile_transfer_knowledge(load_recipe(RECIPE_PATH))
    history = (
        {
            "action": {"action": "read_file", "path": "missing.py"},
            "output": {"error": "file does not exist: missing.py"},
        },
    )

    rendered = format_transfer_knowledge(
        transfer.to_dict(), history=history
    )

    assert "No current-workspace file has been successfully inspected yet." in rendered
    assert "has already been successfully inspected" not in rendered


def test_transfer_rendering_does_not_modify_artifact_json():
    before = TRANSFER_PATH.read_bytes()
    transfer = load_transfer_knowledge(TRANSFER_PATH)

    format_transfer_knowledge(transfer.to_dict())

    assert TRANSFER_PATH.read_bytes() == before


def test_repeat_preserves_transfer_context_and_individual_results(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task03_resource_path",
        tmp_path / "tasks" / "task03_resource_path",
    )
    transfer = compile_transfer_knowledge(load_recipe(RECIPE_PATH))

    summary, summary_path = run_repeated_benchmark(
        tmp_path,
        "task03_resource_path",
        MockModelAdapter(),
        repeat=2,
        transfer_knowledge=transfer,
        max_steps=1,
    )

    assert summary.total_runs == 2
    assert summary.context_mode == "transfer_knowledge"
    assert summary.source_recipe_id == transfer.source_recipe_id
    assert summary.transfer_knowledge_id == transfer.transfer_knowledge_id
    assert summary_path.exists()
    for individual in summary.individual_runs:
        persisted = json.loads(
            Path(individual.result_path).read_text(encoding="utf-8")
        )
        assert persisted["context_mode"] == "transfer_knowledge"
        assert persisted["source_recipe_id"] == transfer.source_recipe_id
        assert persisted["transfer_knowledge_id"] == (
            transfer.transfer_knowledge_id
        )
        assert persisted["recipe_id"] is None
