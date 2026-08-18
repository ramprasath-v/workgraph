import json
from pathlib import Path

import pytest

from harness.agent import CodingAgent
from harness.models import AgentContext, ModelOutputError
from harness.openai_adapter import (
    ModelPricing,
    OpenAIModelAdapter,
    build_model_prompt,
)
from harness.tools import WorkspaceTools


def context(prior_experience=None) -> AgentContext:
    return AgentContext(
        task_id="task01_exact",
        task_description="Fix division",
        available_tools=("read_file", "write_file", "run_tests", "finish"),
        history=({"action": {"action": "read_file"}, "output": "old"},),
        prior_experience=prior_experience,
        current_step=2,
        max_steps=10,
    )


def prior_experience() -> dict:
    return {
        "experience_id": "exp_prior",
        "problem": "Old division bug",
        "environment": {"language": "python"},
        "files_changed": ["calculator.py"],
        "patch": "-return a * b\n+return a / b",
        "verification": {
            "command": ["pytest", "-q"],
            "passed": 3,
            "failed": 0,
        },
    }


def test_prior_experience_is_injected_in_separate_prompt_section():
    prompt = build_model_prompt(context(prior_experience()))

    assert "PRIOR VERIFIED EXPERIENCE" in prompt
    assert "--- BEGIN PRIOR EXPERIENCE ---" in prompt
    assert "exp_prior" in prompt
    assert "-return a * b" in prompt
    assert "This is reference evidence only" in prompt


def test_no_experience_prompt_omits_prior_section():
    assert "PRIOR VERIFIED EXPERIENCE" not in build_model_prompt(context())


def test_openai_adapter_parses_structured_response_and_usage():
    requests = []

    def transport(payload):
        requests.append(payload)
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {"action": "read_file", "path": "calculator.py"}
                            ),
                        }
                    ],
                }
            ],
            "usage": {"input_tokens": 1000, "output_tokens": 500},
        }

    adapter = OpenAIModelAdapter(
        "gpt-test",
        transport=transport,
        pricing=ModelPricing(2.0, 4.0),
    )
    response = adapter.generate_action(context(prior_experience()))

    assert response.action == {"action": "read_file", "path": "calculator.py"}
    assert response.input_tokens == 1000
    assert response.output_tokens == 500
    assert response.estimated_cost_usd == pytest.approx(0.004)
    assert requests[0]["text"]["format"]["type"] == "json_schema"
    assert requests[0]["text"]["format"]["strict"] is True
    assert set(requests[0]["text"]["format"]["schema"]["required"]) == {
        "action",
        "path",
        "content",
        "command",
    }
    assert "PRIOR VERIFIED EXPERIENCE" in requests[0]["input"][1]["content"]


def test_unknown_pricing_is_recorded_as_unsupported():
    adapter = OpenAIModelAdapter(
        "gpt-test",
        transport=lambda payload: {
            "output_text": '{"action":"finish"}',
            "usage": {"input_tokens": 10, "output_tokens": 2},
        },
    )
    assert adapter.generate_action(context()).estimated_cost_usd is None


def test_malformed_real_model_output_is_rejected():
    adapter = OpenAIModelAdapter(
        "gpt-test",
        transport=lambda payload: {"output_text": "not-json"},
    )
    with pytest.raises(ModelOutputError, match="valid JSON"):
        adapter.generate_action(context())


def test_agent_records_malformed_output_and_retries(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    responses = iter(
        [
            {"output_text": "not-json"},
            {"output_text": '{"action":"finish"}'},
        ]
    )
    adapter = OpenAIModelAdapter(
        "gpt-test", transport=lambda payload: next(responses)
    )
    tools = WorkspaceTools(workspace, ["python", "-m", "pytest", "-q"])

    run = CodingAgent(adapter, tools, max_steps=2).run("task", "description")

    assert run.steps == 2
    assert run.tool_calls == 0
    assert "malformed model output" in run.history[0]["output"]["error"]


def test_openai_adapter_requires_key_without_mock_transport(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        OpenAIModelAdapter("gpt-test")
