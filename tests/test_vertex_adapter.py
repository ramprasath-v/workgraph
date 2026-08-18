import json
from types import SimpleNamespace

import pytest

import harness.runner as runner_module
from harness.models import AgentContext, ModelOutputError, ModelPricing
from harness.vertex_adapter import VertexGeminiAdapter


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = FakeModels(response, error)


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


def test_vertex_parses_structured_action_and_usage():
    response = SimpleNamespace(
        parsed=None,
        text=json.dumps(
            {
                "action": "read_file",
                "path": "calculator.py",
                "content": None,
                "command": None,
            }
        ),
        usage_metadata=SimpleNamespace(
            prompt_token_count=120,
            candidates_token_count=30,
            total_token_count=155,
        ),
    )
    client = FakeClient(response)
    adapter = VertexGeminiAdapter(
        "gemini-test",
        project="test-project",
        client=client,
        pricing=ModelPricing(1.0, 2.0),
    )

    result = adapter.generate_action(context())

    assert result.action == {"action": "read_file", "path": "calculator.py"}
    assert result.input_tokens == 120
    assert result.output_tokens == 30
    assert result.total_tokens == 155
    assert result.estimated_cost_usd == pytest.approx(0.00018)
    config = client.models.calls[0]["config"]
    assert config["response_mime_type"] == "application/json"
    assert config["response_json_schema"]["properties"]["action"]["enum"]


def test_vertex_injects_the_shared_prior_experience_prompt():
    client = FakeClient(
        SimpleNamespace(
            parsed={"action": "finish"},
            text=None,
            usage_metadata=None,
        )
    )
    adapter = VertexGeminiAdapter(
        "gemini-test", project="test-project", client=client
    )

    adapter.generate_action(context(prior_experience()))

    prompt = client.models.calls[0]["contents"]
    assert "PRIOR VERIFIED EXPERIENCE" in prompt
    assert "--- BEGIN PRIOR EXPERIENCE ---" in prompt
    assert "exp_prior" in prompt
    assert "-return a * b" in prompt
    assert "This is reference evidence only" in prompt


def test_vertex_rejects_malformed_structured_output():
    client = FakeClient(
        SimpleNamespace(parsed=None, text="not-json", usage_metadata=None)
    )
    adapter = VertexGeminiAdapter(
        "gemini-test", project="test-project", client=client
    )

    with pytest.raises(ModelOutputError, match="structured JSON"):
        adapter.generate_action(context())


def test_vertex_requires_project_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT is required"):
        VertexGeminiAdapter("gemini-test", client=FakeClient())


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (RuntimeError("RESOURCE_EXHAUSTED quota 429"), "quota exceeded"),
        (RuntimeError("PERMISSION_DENIED 403"), "permission denied"),
        (RuntimeError("DefaultCredentialsError"), "authentication failed"),
        (RuntimeError("model not found 404"), "model unavailable"),
    ],
)
def test_vertex_provider_errors_are_classified(error, message):
    adapter = VertexGeminiAdapter(
        "gemini-test",
        project="test-project",
        client=FakeClient(error=error),
    )
    with pytest.raises(RuntimeError, match=message):
        adapter.generate_action(context())


def test_runner_selects_vertex_provider(monkeypatch):
    created = []

    class SelectedVertex:
        def __init__(self, name, pricing=None):
            self.name = name
            self.provider = "vertex"
            created.append((name, pricing))

    monkeypatch.setattr(runner_module, "VertexGeminiAdapter", SelectedVertex)

    adapter = runner_module._model_from_name(
        "gemini-2.5-flash", provider="vertex"
    )

    assert adapter.provider == "vertex"
    assert created == [("gemini-2.5-flash", None)]
