from contextlib import nullcontext
from pathlib import Path

import pytest

import harness.runner as runner_module
from harness.models import AgentContext, ModelOutputError
from harness.prompting import build_model_prompt
from harness.transformers_adapter import (
    TransformersDependencyError,
    TransformersDeviceError,
    TransformersModelAdapter,
    TransformersModelLoadError,
    TransformersOutOfMemoryError,
)
from transfer.schema import load_transfer_knowledge


class FakeTokenizer:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.chat_calls = []
        self.tokenize_calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.chat_calls.append((messages, kwargs))
        return "rendered-chat-template"

    def __call__(self, rendered, **kwargs):
        self.tokenize_calls.append((rendered, kwargs))
        return {"input_ids": [[1, 2, 3, 4]]}

    def decode(self, tokens, **kwargs):
        assert tokens == [8, 9]
        assert kwargs == {"skip_special_tokens": True}
        return next(self.outputs)


class FakeModel:
    device = None

    def __init__(self, error=None):
        self.error = error
        self.generate_calls = []
        self.eval_calls = 0

    def eval(self):
        self.eval_calls += 1

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        if self.error:
            raise self.error
        return [[1, 2, 3, 4, 8, 9]]


class FakeTorch:
    def no_grad(self):
        return nullcontext()


def context(prior_context=None) -> AgentContext:
    return AgentContext(
        task_id="task03_resource_path",
        task_description="Fix bundled resource loading.",
        available_tools=(
            "list_files",
            "read_file",
            "write_file",
            "run_tests",
            "finish",
        ),
        prior_experience=prior_context,
        current_step=1,
        max_steps=8,
    )


def adapter_for(output, *, model=None):
    tokenizer = FakeTokenizer([output])
    fake_model = model or FakeModel()
    adapter = TransformersModelAdapter(
        "test/model",
        tokenizer=tokenizer,
        model=fake_model,
        torch_module=FakeTorch(),
        max_new_tokens=64,
        temperature=0,
    )
    return adapter, tokenizer, fake_model


def test_transformers_parses_first_valid_json_action_and_counts_tokens():
    adapter, tokenizer, model = adapter_for(
        'not JSON {broken} then {"action":"read_file",'
        '"path":"module.py","content":null}'
    )

    response = adapter.generate_action(context())

    assert response.action == {"action": "read_file", "path": "module.py"}
    assert response.input_tokens == 4
    assert response.output_tokens == 2
    assert response.total_tokens == 6
    assert response.estimated_cost_usd == 0.0
    assert model.generate_calls[0]["max_new_tokens"] == 64
    assert model.generate_calls[0]["do_sample"] is False
    messages, options = tokenizer.chat_calls[0]
    assert messages[0]["role"] == "system"
    assert "exactly one JSON tool action" in messages[0]["content"]
    assert messages[1]["content"] == build_model_prompt(context())
    assert options == {"tokenize": False, "add_generation_prompt": True}


def test_transformers_model_and_tokenizer_load_only_once():
    tokenizer = FakeTokenizer(
        ['{"action":"finish"}', '{"action":"run_tests"}']
    )
    model = FakeModel()
    tokenizer_loads = []
    model_loads = []

    def load_tokenizer(name):
        tokenizer_loads.append(name)
        return tokenizer

    def load_model(name, **kwargs):
        model_loads.append((name, kwargs))
        return model

    adapter = TransformersModelAdapter(
        "test/model",
        tokenizer_loader=load_tokenizer,
        model_loader=load_model,
        max_new_tokens=32,
        temperature=0,
    )

    assert adapter.generate_action(context()).action == {"action": "finish"}
    assert adapter.generate_action(context()).action == {"action": "run_tests"}
    assert tokenizer_loads == ["test/model"]
    assert len(model_loads) == 1
    assert model_loads[0][0] == "test/model"
    assert model_loads[0][1]["device_map"] == "auto"
    assert model.eval_calls == 1


def test_transformers_uses_exact_transfer_knowledge_prompt():
    transfer = load_transfer_knowledge(
        Path(__file__).resolve().parents[1]
        / "transfer_knowledge"
        / "transfer_a4142b399f8684e6a75fda4a625ed4d8.json"
    )
    agent_context = context(transfer.to_dict())
    adapter, tokenizer, _ = adapter_for('{"action":"list_files"}')

    adapter.generate_action(agent_context)

    user_prompt = tokenizer.chat_calls[0][0][1]["content"]
    assert user_prompt == build_model_prompt(agent_context)
    assert "PRIOR VERIFIED TRANSFER KNOWLEDGE" in user_prompt
    assert "Concepts such as __file__ describe implementation mechanisms" in user_prompt


def test_transformers_rejects_malformed_model_output():
    adapter, _, _ = adapter_for("markdown and shell text only")

    with pytest.raises(ModelOutputError, match="no valid JSON action"):
        adapter.generate_action(context())


def test_transformers_classifies_cuda_out_of_memory():
    adapter, _, _ = adapter_for(
        '{"action":"finish"}', model=FakeModel(RuntimeError("CUDA out of memory"))
    )

    with pytest.raises(TransformersOutOfMemoryError, match="out of device memory"):
        adapter.generate_action(context())


@pytest.mark.parametrize(
    ("error", "error_type"),
    [
        (RuntimeError("no compatible device"), TransformersDeviceError),
        (RuntimeError("model files unavailable"), TransformersModelLoadError),
    ],
)
def test_transformers_classifies_model_loading_errors(error, error_type):
    adapter = TransformersModelAdapter(
        "test/model",
        tokenizer_loader=lambda name: FakeTokenizer(['{"action":"finish"}']),
        model_loader=lambda name, **kwargs: (_ for _ in ()).throw(error),
        max_new_tokens=16,
        temperature=0,
    )

    with pytest.raises(error_type):
        adapter.generate_action(context())


def test_transformers_missing_optional_dependencies_is_clear(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def missing_optional(name, *args, **kwargs):
        if name in {"torch", "transformers"}:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_optional)
    adapter = TransformersModelAdapter(
        "test/model", max_new_tokens=16, temperature=0
    )

    with pytest.raises(
        TransformersDependencyError,
        match="requirements-transformers.txt",
    ):
        adapter.generate_action(context())


def test_runner_selects_transformers_provider(monkeypatch):
    selected = {}

    class SelectedTransformers:
        provider = "transformers"

        def __init__(self, name):
            selected["name"] = name
            self.name = name

    monkeypatch.setattr(
        runner_module, "TransformersModelAdapter", SelectedTransformers
    )

    adapter = runner_module._model_from_name(
        "Qwen/Qwen2.5-7B-Instruct", provider="transformers"
    )

    assert adapter.provider == "transformers"
    assert selected["name"] == "Qwen/Qwen2.5-7B-Instruct"


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"TRANSFORMERS_MAX_NEW_TOKENS": "0"}, "positive integer"),
        ({"TRANSFORMERS_TEMPERATURE": "-1"}, "non-negative number"),
    ],
)
def test_transformers_generation_configuration_validation(
    monkeypatch, environment, message
):
    for name in ("TRANSFORMERS_MAX_NEW_TOKENS", "TRANSFORMERS_TEMPERATURE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        TransformersModelAdapter("test/model", tokenizer=object(), model=object())
