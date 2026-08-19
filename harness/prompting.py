"""Provider-neutral action schema and coding-agent prompt rendering."""

from __future__ import annotations

import json
from typing import Any

from .models import AgentContext


ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "list_files",
                "read_file",
                "write_file",
                "run_command",
                "run_tests",
                "finish",
            ],
        },
        "path": {"type": ["string", "null"]},
        "content": {"type": ["string", "null"]},
        "command": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
    },
    "required": ["action", "path", "content", "command"],
    "additionalProperties": False,
}

TOOL_DEFINITIONS = {
    "list_files": "List regular files in the active workspace.",
    "read_file": "Read one workspace file. Requires path.",
    "write_file": "Write one workspace file. Requires path and complete content.",
    "run_command": "Run an allowlisted test command. Requires command string array.",
    "run_tests": "Run the task's deterministic test command.",
    "finish": "Stop when the task is ready for final deterministic verification.",
}


def format_prior_experience(experience: dict[str, Any]) -> str:
    verification = experience["verification"]
    environment = json.dumps(experience["environment"], sort_keys=True)
    files = ", ".join(experience["files_changed"]) or "(none)"
    return (
        "PRIOR VERIFIED EXPERIENCE\n"
        "--- BEGIN PRIOR EXPERIENCE ---\n"
        f"Experience ID: {experience['experience_id']}\n"
        f"Problem:\n{experience['problem']}\n\n"
        f"Environment:\n{environment}\n\n"
        f"Files changed:\n{files}\n\n"
        f"Patch:\n{experience['patch']}\n"
        "Verification:\n"
        f"{verification['passed']} passed, {verification['failed']} failed; "
        f"command={json.dumps(verification['command'])}\n"
        "--- END PRIOR EXPERIENCE ---\n"
        "This is reference evidence only. Do not assume it has been applied. "
        "Inspect and modify the current workspace using the available tools."
    )


def format_prior_recipe(
    recipe: dict[str, Any],
    history: tuple[dict[str, Any], ...] = (),
) -> str:
    files = "\n".join(f"- {path}" for path in recipe["target_files"])
    instructions = {
        step["step"]: step["instruction"] for step in recipe["steps"]
    }
    constraint = instructions.get(2, recipe["problem"])
    goal = instructions.get(3, recipe["problem"])
    concepts = recipe.get("implementation_concepts", [])
    concept_section = ""
    if concepts:
        label = (
            "Implementation concept"
            if len(concepts) == 1
            else "Implementation concepts"
        )
        concept_lines = "\n".join(f"- {concept}" for concept in concepts)
        concept_section = f"{label}:\n{concept_lines}\n\n"
    verification = recipe["verification"]
    target_files = set(recipe["target_files"])
    inspected_targets = {
        action["path"]
        for entry in history
        if isinstance((action := entry.get("action")), dict)
        and action.get("action") == "read_file"
        and action.get("path") in target_files
        and isinstance(entry.get("output"), str)
    }
    if inspected_targets:
        next_action_guidance = (
            "The target file has already been inspected.\n"
            "Use the file contents from previous tool output and the verified "
            "guidance to continue toward the fix.\n"
            "Do not reread the same file unless new information makes that "
            "necessary.\n"
            "If you understand the required change, the next useful action may "
            "be to modify the target file."
        )
    else:
        next_action_guidance = (
            "The target file has not yet been inspected. "
            "Inspect it before modifying it."
        )
    return (
        "PRIOR VERIFIED EXPERIENCE\n"
        "--- BEGIN PRIOR EXPERIENCE ---\n\n"
        "Useful facts from a previous successful run:\n\n"
        f"Target file(s):\n{files}\n\n"
        f"Goal:\n{goal}\n\n"
        f"Constraint:\n{constraint}\n\n"
        f"{concept_section}"
        "Previous verification:\n"
        f"{verification['previously_passed']} passed / "
        f"{verification['previously_failed']} failed\n\n"
        "--- END PRIOR EXPERIENCE ---\n\n"
        "Guidance only. Do not attempt all steps at once.\n"
        "Choose ONLY the next single tool action.\n"
        f"{next_action_guidance}"
    )


def format_transfer_knowledge(
    knowledge: dict[str, Any],
    history: tuple[dict[str, Any], ...] = (),
) -> str:
    principles = "\n".join(
        f"- {principle}" for principle in knowledge["principles"]
    )
    concepts = "\n".join(
        f"- {concept}" for concept in knowledge["implementation_concepts"]
    )
    has_successful_file_read = any(
        isinstance((action := entry.get("action")), dict)
        and action.get("action") == "read_file"
        and isinstance(entry.get("output"), str)
        for entry in history
    )
    if has_successful_file_read:
        grounding = (
            "A current-workspace file has already been successfully inspected.\n"
            "Use the current workspace contents and the transferred principle "
            "to determine whether and where it applies."
        )
    else:
        grounding = (
            "No current-workspace file has been successfully inspected yet.\n"
            "Discovering the workspace structure and inspecting its source files "
            "is usually the appropriate next step."
        )
    return (
        "PRIOR VERIFIED TRANSFER KNOWLEDGE\n\n"
        "A previous successful task established:\n\n"
        f"Principle:\n{principles}\n\n"
        f"Implementation concept:\n{concepts}\n\n"
        "TRANSFER GUIDANCE\n\n"
        "This came from a different task.\n"
        "Do not assume filenames, paths, functions, or project structure are the "
        "same.\n"
        "Concepts such as __file__ describe implementation mechanisms; do not "
        "treat them as filenames or workspace paths to inspect.\n"
        f"{grounding}\n"
        "Choose ONLY the next single tool action."
    )


def format_scout_handoff(handoff: dict[str, Any]) -> str:
    files = "\n".join(f"- {path}" for path in handoff["files_inspected"])
    observations = "\n".join(f"- {item}" for item in handoff["observations"])
    investigation = "\n".join(
        f"- {item}" for item in handoff["recommended_investigation"]
    )
    constraints = "\n".join(f"- {item}" for item in handoff["constraints"])
    return (
        "CURRENT-TASK SCOUT HANDOFF\n\n"
        "A scout inspected this current task before you started.\n\n"
        f"Observed files/areas:\n{files or '- (none)'}\n\n"
        f"Diagnosis / useful observations:\n{observations}\n"
        f"- Suspected area: {handoff['suspected_area']}\n\n"
        f"Recommended investigation:\n{investigation}\n\n"
        f"Constraints:\n{constraints}\n\n"
        "This is guidance only. You must still inspect, edit, and verify using "
        "normal tools.\n"
        "Choose ONLY the next single tool action."
    )


def format_compact_scout(knowledge: dict[str, Any]) -> str:
    principles = "\n".join(
        f"- {principle}" for principle in knowledge["principles"]
    )
    concepts = "\n".join(
        f"- {concept}" for concept in knowledge["implementation_concepts"]
    )
    return (
        "COMPACT CURRENT-TASK SCOUT KNOWLEDGE\n\n"
        "A read-only scout inspected this current task and its findings were "
        "compacted into general guidance.\n\n"
        f"Principles:\n{principles}\n\n"
        f"Implementation concepts:\n{concepts}\n\n"
        "This is guidance only.\n"
        "Inspect the workspace and determine whether and where it applies.\n"
        "Choose ONLY the next single tool action."
    )


def build_model_prompt(context: AgentContext) -> str:
    tools = {
        name: TOOL_DEFINITIONS[name]
        for name in context.available_tools
        if name in TOOL_DEFINITIONS
    }
    sections = [
        f"TASK\n{context.task_description}",
        f"TASK ID\n{context.task_id}",
        f"AVAILABLE TOOLS\n{json.dumps(tools, indent=2, sort_keys=True)}",
        (
            f"STEP BUDGET\nCurrent step: {context.current_step}; "
            f"remaining including this step: "
            f"{context.max_steps - context.current_step + 1}"
        ),
    ]
    if context.prior_experience is not None:
        if "compact_scout_version" in context.prior_experience:
            sections.append(format_compact_scout(context.prior_experience))
        elif "scout_handoff_version" in context.prior_experience:
            sections.append(format_scout_handoff(context.prior_experience))
        elif "transfer_version" in context.prior_experience:
            sections.append(
                format_transfer_knowledge(
                    context.prior_experience, history=context.history
                )
            )
        elif "recipe_version" in context.prior_experience:
            sections.append(
                format_prior_recipe(
                    context.prior_experience, history=context.history
                )
            )
        else:
            sections.append(format_prior_experience(context.prior_experience))
    sections.append(
        "PREVIOUS ACTIONS AND TOOL OUTPUTS\n"
        + json.dumps(context.history, indent=2, ensure_ascii=False)
    )
    sections.append(
        "Return exactly one structured action. Never emit or request shell script text."
    )
    return "\n\n".join(sections)
