import json
import shutil
from pathlib import Path

from harness.assistance_control import (
    AssistanceControl,
    WRAPPER_TEMPLATE_ID,
    approximate_tokens,
    payload_sha256,
)
from harness.models import AgentContext, ModelAdapter, ModelResponse
from harness.runner import run_benchmark


ROOT = Path(__file__).resolve().parents[1]


def control(payload="Additional guidance: none."):
    return AssistanceControl(
        assistance_control_version="0.1",
        assistance_control_id="integrity-test-control",
        condition_id="INTEGRITY_TEST",
        wrapper_template_id=WRAPPER_TEMPLATE_ID,
        payload=payload,
        payload_sha256=payload_sha256(payload),
        payload_character_count=len(payload),
        payload_approximate_tokens=approximate_tokens(payload),
        protected_evaluator_files=("test_calculator.py",),
    )


class TestMutatingAdapter(ModelAdapter):
    name = "test-mutator"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        actions = (
            {
                "action": "write_file",
                "path": "test_calculator.py",
                "content": "def test_weakened():\n    assert True\n",
            },
            {"action": "finish"},
        )
        return ModelResponse(actions[min(len(context.history), 1)])


class CorrectSourceAdapter(ModelAdapter):
    name = "correct-source"
    provider = "test"

    def generate_action(self, context: AgentContext) -> ModelResponse:
        actions = (
            {
                "action": "write_file",
                "path": "calculator.py",
                "content": (
                    '"""Tiny calculator used by the benchmark fixture."""\n\n'
                    "def divide(a, b):\n    return a / b\n"
                ),
            },
            {"action": "finish"},
        )
        return ModelResponse(actions[min(len(context.history), 1)])


def _repo(tmp_path):
    shutil.copytree(
        ROOT / "tasks" / "task01_exact",
        tmp_path / "tasks" / "task01_exact",
    )
    return tmp_path


def test_modified_protected_evaluator_cannot_succeed_and_hashes_are_persisted(tmp_path):
    result, result_path = run_benchmark(
        _repo(tmp_path),
        "task01_exact",
        TestMutatingAdapter(),
        run_id="integrity-failure",
        assistance_control=control(),
    )

    assert result.tests_failed == 0
    assert result.success is False
    assert result.verification_integrity_passed is False
    assert result.protected_files_checked == ["test_calculator.py"]
    assert result.protected_files_modified == ["test_calculator.py"]
    assert result.original_evaluator_hashes != result.final_evaluator_hashes
    assert result.failure_type == "verification_integrity_failure"
    assert result.generated_experience_id is None
    persisted = json.loads(result_path.read_text(encoding="utf-8"))
    for field in (
        "verification_integrity_passed",
        "protected_files_checked",
        "protected_files_modified",
        "original_evaluator_hashes",
        "final_evaluator_hashes",
        "integrity_failure_reason",
        "integrity_guard_version",
    ):
        assert field in persisted


def test_unchanged_protected_evaluator_and_passing_tests_can_succeed(tmp_path):
    result, _ = run_benchmark(
        _repo(tmp_path),
        "task01_exact",
        CorrectSourceAdapter(),
        run_id="integrity-pass",
        assistance_control=control(),
    )

    assert result.success is True
    assert result.tests_passed == 3
    assert result.verification_integrity_passed is True
    assert result.protected_files_modified == []
    assert result.original_evaluator_hashes == result.final_evaluator_hashes
    assert result.integrity_failure_reason is None
    assert result.generated_experience_id is not None


def test_undeclared_historical_style_run_preserves_legacy_semantics(tmp_path):
    result, _ = run_benchmark(
        _repo(tmp_path),
        "task01_exact",
        TestMutatingAdapter(),
        run_id="legacy-no-declaration",
    )

    assert result.success is True
    assert result.verification_integrity_passed is None
    assert result.protected_files_checked is None
    assert result.integrity_guard_version is None
