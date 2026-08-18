import json
import shutil
import urllib.error
from pathlib import Path

import pytest

import harness.runner as runner_module
from experience.schema import ExperienceRecord, Verification
from harness.models import AgentContext, ModelOutputError
from harness.ollama_adapter import (
    OllamaModelAdapter,
    OllamaTimeoutError,
    OllamaUnavailableError,
)
from harness.runner import run_comparison, run_ollama_diagnostics


REPO_ROOT = Path(__file__).resolve().parents[1]


def context(prior_experience=None) -> AgentContext:
    return AgentContext(
        task_id="task02_config_path",
        task_description="Fix configuration loading",
        available_tools=("list_files", "read_file", "write_file", "run_tests", "finish"),
        history=({"action": {"action": "list_files"}, "output": ["app.py"]},),
        prior_experience=prior_experience,
        current_step=2,
        max_steps=20,
    )


def prior_experience() -> dict:
    return {
        "experience_id": "exp_gemini_task02",
        "problem": "Configuration loading failed",
        "environment": {"language": "python"},
        "files_changed": ["app.py"],
        "patch": "-old\n+new",
        "verification": {
            "command": ["pytest", "-q", "test_app.py"],
            "passed": 4,
            "failed": 0,
        },
    }


def experience_record() -> ExperienceRecord:
    return ExperienceRecord(
        experience_id="exp_prior",
        task_id="task01_exact",
        producer_model="vertex",
        problem="Fix division",
        environment={"language": "python"},
        files_changed=["calculator.py"],
        patch="-    return a * b\n+    return a / b\n",
        verification=Verification(
            command=["python", "-m", "pytest", "-q", "test_calculator.py"],
            passed=3,
            failed=0,
        ),
        successful=True,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        created_at="2026-01-01T00:00:01+00:00",
    )


def test_ollama_default_timeout_is_180_seconds(monkeypatch):
    monkeypatch.delenv("OLLAMA_TIMEOUT_SECONDS", raising=False)
    adapter = OllamaModelAdapter("qwen-test:7b", transport=lambda payload: {})
    assert adapter.timeout_seconds == 180


def test_ollama_custom_timeout_from_environment(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "245.5")
    adapter = OllamaModelAdapter("qwen-test:7b", transport=lambda payload: {})
    assert adapter.timeout_seconds == 245.5


@pytest.mark.parametrize("value", ["0", "-10", "abc"])
def test_ollama_invalid_timeout_is_rejected(monkeypatch, value):
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", value)
    with pytest.raises(
        ValueError, match="OLLAMA_TIMEOUT_SECONDS must be a positive number"
    ):
        OllamaModelAdapter("qwen-test:7b", transport=lambda payload: {})


def test_configured_timeout_is_passed_to_http(monkeypatch):
    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"message":{"content":"{\\"action\\":\\"finish\\"}"}}'

    def urlopen(request, timeout):
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "321")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    adapter = OllamaModelAdapter("qwen-test:7b")

    adapter.generate_action(context())

    assert observed["timeout"] == 321


def test_ollama_timeout_error_is_actionable(monkeypatch):
    def timed_out(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "180")
    monkeypatch.setattr("urllib.request.urlopen", timed_out)
    adapter = OllamaModelAdapter("qwen-test:7b")

    with pytest.raises(OllamaTimeoutError) as caught:
        adapter.generate_action(context())

    message = str(caught.value)
    assert "did not respond" in message
    assert "180 seconds" in message
    assert "increase OLLAMA_TIMEOUT_SECONDS" in message


def test_debug_mode_is_off_by_default(monkeypatch, capsys):
    monkeypatch.delenv("OLLAMA_DEBUG", raising=False)
    monkeypatch.delenv("OLLAMA_DEBUG_PROMPT", raising=False)
    adapter = OllamaModelAdapter(
        "qwen-test:7b",
        transport=lambda payload: {"message": {"content": '{"action":"finish"}'}},
    )

    adapter.generate_action(context())

    assert capsys.readouterr().err == ""


def test_debug_metadata_enabled_but_prompt_hidden(monkeypatch, capsys):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"message":{"content":"{\\"action\\":\\"finish\\"}"}}'

    monkeypatch.setenv("OLLAMA_DEBUG", "1")
    monkeypatch.delenv("OLLAMA_DEBUG_PROMPT", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Response())
    adapter = OllamaModelAdapter("qwen-test:7b")

    adapter.generate_action(context())

    debug = capsys.readouterr().err
    for field in (
        '"model"',
        '"endpoint"',
        '"timeout_seconds"',
        '"message_count"',
        '"message_character_counts"',
        '"total_prompt_characters"',
        '"schema_characters"',
        '"format_sent"',
        '"streaming"',
        '"request_body_bytes"',
        '"agent_step"',
        '"history_entries"',
    ):
        assert field in debug
    assert "Fix configuration loading" not in debug
    assert "prompt-begin" not in debug
    for phase in (
        "prompt_rendering",
        "json_serialization",
        "http_request_start",
        "http_headers",
        "response_body_read",
        "http_round_trip",
        "structured_output_parsing",
    ):
        assert phase in debug


def test_debug_prompt_requires_explicit_setting(monkeypatch, capsys):
    monkeypatch.setenv("OLLAMA_DEBUG", "1")
    monkeypatch.setenv("OLLAMA_DEBUG_PROMPT", "1")
    adapter = OllamaModelAdapter(
        "qwen-test:7b",
        transport=lambda payload: {"message": {"content": '{"action":"finish"}'}},
    )

    adapter.generate_action(context())

    debug = capsys.readouterr().err
    assert "prompt-begin" in debug
    assert "Fix configuration loading" in debug


def test_diagnostic_trivial_request_uses_no_schema():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {
            "message": {"content": "OK"},
            "prompt_eval_count": 4,
            "eval_count": 1,
        }

    result = OllamaModelAdapter(
        "qwen-test:7b", transport=transport
    ).diagnose_request("Reply with only OK", structured_schema=False)

    assert result.success is True
    assert result.structured_schema is False
    assert result.input_tokens == 4
    assert "format" not in calls[0]


def test_diagnostic_structured_request_uses_shared_schema():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"message": {"content": '{"action":"finish"}'}}

    result = OllamaModelAdapter(
        "qwen-test:7b", transport=transport
    ).diagnose_request("Return an action", structured_schema=True)

    assert result.success is True
    assert result.structured_schema is True
    assert calls[0]["format"]["properties"]["action"]["enum"]


def test_diagnostic_task02_uses_actual_first_turn_prompt(capsys):
    calls = []

    def transport(payload):
        calls.append(payload)
        content = (
            '{"action":"finish"}' if "format" in payload else "OK"
        )
        return {"message": {"content": content}}

    adapter = OllamaModelAdapter("qwen-test:7b", transport=transport)

    results = run_ollama_diagnostics(
        REPO_ROOT, "task02_config_path", adapter
    )

    assert len(results) == 3
    assert all(result.success for _, result in results)
    task_prompt = calls[2]["messages"][1]["content"]
    assert "TASK ID\ntask02_config_path" in task_prompt
    assert "Application configuration loading is unreliable" in task_prompt
    assert "PREVIOUS ACTIONS AND TOOL OUTPUTS\n[]" in task_prompt
    assert "A - trivial" in capsys.readouterr().out


def test_comparison_continues_and_records_ollama_timeout(tmp_path: Path):
    shutil.copytree(
        REPO_ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )
    calls = 0

    def transport(payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OllamaTimeoutError(
                "Ollama model 'qwen-test:7b' did not respond within the "
                "configured timeout of 180 seconds; increase OLLAMA_TIMEOUT_SECONDS"
            )
        if calls == 2:
            content = json.dumps(
                {
                    "action": "write_file",
                    "path": "calculator.py",
                    "content": "def divide(a, b):\n    return a / b\n",
                }
            )
        else:
            content = '{"action":"finish"}'
        return {"message": {"content": content}}

    adapter = OllamaModelAdapter("qwen-test:7b", transport=transport)

    baseline, experiment = run_comparison(
        tmp_path, "task01_exact", adapter, experience_record()
    )

    assert baseline.success is False
    assert baseline.failure_type == "timeout"
    assert "180 seconds" in baseline.failure_message
    assert baseline.failure_type != "max_steps_exhausted"
    assert experiment.success is True
    assert experiment.failure_type is None
    assert calls >= 3


def test_ollama_parses_structured_action_and_token_usage():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "action": "read_file",
                        "path": "app.py",
                        "content": None,
                        "command": None,
                    }
                ),
            },
            "prompt_eval_count": 80,
            "eval_count": 20,
        }

    adapter = OllamaModelAdapter("qwen-test:7b", transport=transport)
    result = adapter.generate_action(context())

    assert result.action == {"action": "read_file", "path": "app.py"}
    assert result.input_tokens == 80
    assert result.output_tokens == 20
    assert result.total_tokens == 100
    assert result.estimated_cost_usd == 0.0
    assert calls[0]["stream"] is False
    assert calls[0]["format"]["properties"]["action"]["enum"]


def test_ollama_rejects_malformed_json():
    adapter = OllamaModelAdapter(
        "qwen-test:7b",
        transport=lambda payload: {"message": {"content": "not-json"}},
    )
    with pytest.raises(ModelOutputError, match="structured JSON"):
        adapter.generate_action(context())


def test_ollama_unavailable_endpoint_is_clear(monkeypatch):
    def unavailable(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    adapter = OllamaModelAdapter(
        "qwen-test:7b", base_url="http://127.0.0.1:11434"
    )

    with pytest.raises(OllamaUnavailableError, match="start Ollama"):
        adapter.generate_action(context())


def test_ollama_reports_missing_model_pull_command():
    adapter = OllamaModelAdapter(
        "qwen-test:7b",
        transport=lambda payload: {"error": "model not found"},
    )
    with pytest.raises(RuntimeError, match="ollama pull qwen-test:7b"):
        adapter.generate_action(context())


def test_ollama_injects_shared_prior_experience_prompt():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"message": {"content": '{"action":"finish"}'}}

    adapter = OllamaModelAdapter("qwen-test:7b", transport=transport)
    adapter.generate_action(context(prior_experience()))

    prompt = calls[0]["messages"][1]["content"]
    assert "PRIOR VERIFIED EXPERIENCE" in prompt
    assert "--- BEGIN PRIOR EXPERIENCE ---" in prompt
    assert "exp_gemini_task02" in prompt
    assert "-old" in prompt
    assert "This is reference evidence only" in prompt


def test_runner_selects_ollama_provider(monkeypatch):
    created = []

    class SelectedOllama:
        def __init__(self, name):
            self.name = name
            self.provider = "ollama"
            created.append(name)

    monkeypatch.setattr(runner_module, "OllamaModelAdapter", SelectedOllama)

    adapter = runner_module._model_from_name("qwen2.5:7b", provider="ollama")

    assert adapter.provider == "ollama"
    assert created == ["qwen2.5:7b"]
