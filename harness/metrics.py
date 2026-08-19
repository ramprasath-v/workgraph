"""Run metrics representation and JSON persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunResult:
    run_id: str
    task_id: str
    model_provider: str
    model_name: str
    experience_used: bool
    experience_id: str | None
    success: bool
    start_time: str
    end_time: str
    elapsed_seconds: float
    agent_steps: int
    tool_calls: int
    test_command: list[str]
    tests_passed: int
    tests_failed: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    max_steps: int
    trajectory: list[dict[str, object]]
    trajectory_diagnostics: dict[str, object]
    failure_type: str | None = None
    failure_message: str | None = None
    generated_experience_id: str | None = None
    generated_experience_path: str | None = None
    context_mode: str = "none"
    source_experience_id: str | None = None
    recipe_id: str | None = None
    source_recipe_id: str | None = None
    transfer_knowledge_id: str | None = None
    scout_handoff_id: str | None = None
    scout_model: str | None = None
    scout_input_tokens: int = 0
    scout_output_tokens: int = 0
    scout_total_tokens: int = 0
    scout_elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["total_inference_tokens"] = self.total_inference_tokens()
        data["total_inference_elapsed_seconds"] = (
            self.total_inference_elapsed_seconds()
        )
        return data

    def total_inference_tokens(self) -> int:
        return self.total_tokens + self.scout_total_tokens

    def total_inference_elapsed_seconds(self) -> float:
        return round(self.elapsed_seconds + self.scout_elapsed_seconds, 6)

    def write_json(self, results_dir: Path) -> Path:
        results_dir.mkdir(parents=True, exist_ok=True)
        destination = results_dir / f"{self.run_id}.json"
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination
