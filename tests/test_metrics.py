import json
from pathlib import Path

from harness.metrics import RunResult


def test_metrics_serialization(tmp_path: Path):
    result = RunResult(
        run_id="run-1",
        task_id="task-1",
        model_provider="mock",
        model_name="mock",
        experience_used=False,
        experience_id=None,
        success=True,
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-01-01T00:00:01+00:00",
        elapsed_seconds=1.0,
        agent_steps=2,
        tool_calls=1,
        test_command=["python", "-m", "pytest", "-q"],
        tests_passed=1,
        tests_failed=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        estimated_cost_usd=0.0,
        max_steps=20,
        trajectory=[
            {
                "step": 1,
                "action": "read_file",
                "target": "app.py",
                "outcome": "success",
            }
        ],
        trajectory_diagnostics={"file_reads": 1},
    )
    output = result.write_json(tmp_path)
    assert json.loads(output.read_text(encoding="utf-8")) == result.to_dict()
