import json
import sys
from pathlib import Path

from experience.schema import load_experience
from harness.models import AgentContext
from harness.prompting import build_model_prompt, format_prior_recipe
from harness.runner import main
from recipe.compiler import compile_recipe
from recipe.schema import load_recipe


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_EXPERIENCE = (
    REPO_ROOT
    / "experiences"
    / "exp_aedf873f3b13471ea3e0145e4a4c7c2d.json"
)
V01_RECIPE = (
    REPO_ROOT
    / "recipes"
    / "recipe_399fb85ca6f7cf0c8dfbb73fe9c2db6f.json"
)
IMPLEMENTATION_CONCEPT = (
    "For a path relative to the Python module rather than the current working "
    "directory, use __file__ as the path anchor."
)


def context(prior_context=None, history=()) -> AgentContext:
    return AgentContext(
        task_id="task02_config_path",
        task_description="Fix configuration loading",
        available_tools=("read_file", "write_file", "run_tests", "finish"),
        prior_experience=prior_context,
        history=history,
    )


def test_recipe_compilation_is_deterministic_and_does_not_modify_source():
    before = SOURCE_EXPERIENCE.read_bytes()
    experience = load_experience(SOURCE_EXPERIENCE)

    first = compile_recipe(experience)
    second = compile_recipe(experience)

    assert first == second
    assert first.recipe_id == second.recipe_id
    assert first.recipe_version == "0.2"
    assert first.implementation_concepts == [IMPLEMENTATION_CONCEPT]
    assert SOURCE_EXPERIENCE.read_bytes() == before


def test_recipe_is_compact_and_retains_task02_execution_principle():
    experience = load_experience(SOURCE_EXPERIENCE)
    recipe = compile_recipe(experience)
    serialized = json.dumps(recipe.to_dict(), sort_keys=True)

    assert recipe.source_experience_id == experience.experience_id
    assert recipe.target_files == ["app.py"]
    assert recipe.implementation_concepts == [IMPLEMENTATION_CONCEPT]
    assert experience.patch not in serialized
    assert "--- a/app.py" not in serialized
    assert "@@ -" not in serialized
    assert "Path(__file__)" not in serialized
    assert 'path = Path(__file__).parent / "config/settings.json"' not in serialized
    assert "if config_path:" not in serialized
    assert "relative to the directory containing app.py" in serialized
    assert "rather than the process working directory" in serialized
    assert recipe.verification.previously_passed == 4
    assert recipe.verification.previously_failed == 0


def test_recipe_json_round_trip(tmp_path: Path):
    recipe = compile_recipe(load_experience(SOURCE_EXPERIENCE))

    output = recipe.write_json(tmp_path / "recipes")

    assert output.name == f"{recipe.recipe_id}.json"
    assert load_recipe(output) == recipe
    assert load_recipe(output).implementation_concepts == [IMPLEMENTATION_CONCEPT]


def test_v01_recipe_without_implementation_concepts_still_loads_and_renders():
    recipe = load_recipe(V01_RECIPE)

    prompt = format_prior_recipe(recipe.to_dict())

    assert recipe.recipe_version == "0.1"
    assert recipe.implementation_concepts == []
    assert "Implementation concept:" not in prompt
    assert "Choose ONLY the next single tool action." in prompt


def test_compile_recipe_cli_writes_under_recipes(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness.runner",
            "--root",
            str(tmp_path),
            "--compile-recipe",
            str(SOURCE_EXPERIENCE),
        ],
    )

    assert main() == 0

    outputs = list((tmp_path / "recipes").glob("recipe_*.json"))
    assert len(outputs) == 1
    assert load_recipe(outputs[0]).source_experience_id == (
        "exp_aedf873f3b13471ea3e0145e4a4c7c2d"
    )
    assert f"recipe={outputs[0]}" in capsys.readouterr().out


def test_recipe_prompt_is_separate_and_excludes_raw_diff():
    experience = load_experience(SOURCE_EXPERIENCE)
    recipe = compile_recipe(experience)

    prompt = build_model_prompt(context(recipe.to_dict()))

    assert "PRIOR VERIFIED EXPERIENCE" in prompt
    assert "--- BEGIN PRIOR EXPERIENCE ---" in prompt
    assert "Recommended execution steps:" not in prompt
    assert "Target file(s):\n- app.py" in prompt
    assert "relative to the directory containing app.py" in prompt
    assert "rather than the process working directory" in prompt
    assert "Constraint:\nPreserve caller-supplied config_path behavior." in prompt
    assert f"Implementation concept:\n- {IMPLEMENTATION_CONCEPT}" in prompt
    assert "Choose ONLY the next single tool action." in prompt
    assert "Do not attempt all steps at once." in prompt
    assert "The target file has not yet been inspected." in prompt
    assert "Inspect it before modifying it." in prompt
    assert "4 passed / 0 failed" in prompt
    assert experience.patch not in prompt
    assert "--- a/app.py" not in prompt
    assert 'path = Path(__file__).parent / "config/settings.json"' not in prompt
    assert "if config_path:" not in prompt
    assert len(format_prior_recipe(recipe.to_dict())) < 800


def test_successful_target_read_changes_recipe_next_action_guidance():
    recipe = compile_recipe(load_experience(SOURCE_EXPERIENCE))
    source_marker = "UNIQUE_APP_FILE_CONTENT_FROM_TOOL_OUTPUT"
    history = (
        {
            "action": {"action": "read_file", "path": "app.py"},
            "output": source_marker,
        },
    )

    prompt = build_model_prompt(context(recipe.to_dict(), history=history))

    assert "The target file has already been inspected." in prompt
    assert "Use the file contents from previous tool output" in prompt
    assert "Do not reread the same file" in prompt
    assert "next useful action may be to modify the target file" in prompt
    assert "has not yet been inspected" not in prompt
    assert "inspect it next" not in prompt
    assert prompt.count(source_marker) == 1


def test_failed_target_read_does_not_count_as_inspected():
    recipe = compile_recipe(load_experience(SOURCE_EXPERIENCE))
    history = (
        {
            "action": {"action": "read_file", "path": "app.py"},
            "output": {"error": "file does not exist: app.py"},
        },
    )

    prompt = build_model_prompt(context(recipe.to_dict(), history=history))

    assert "The target file has not yet been inspected." in prompt
    assert "Inspect it before modifying it." in prompt
    assert "has already been inspected" not in prompt


def test_raw_experience_prompt_remains_distinct_and_unchanged():
    experience = load_experience(SOURCE_EXPERIENCE)

    prompt = build_model_prompt(context(experience.to_dict()))

    assert "PRIOR VERIFIED EXPERIENCE" in prompt
    assert "--- BEGIN PRIOR EXPERIENCE ---" in prompt
    assert experience.patch in prompt
    assert "PRIOR VERIFIED EXECUTION RECIPE" not in prompt
    assert "--- BEGIN RECIPE ---" not in prompt
    assert "Choose ONLY the next single tool action." not in prompt
