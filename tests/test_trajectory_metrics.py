import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from analysis.trajectory_metrics import (
    AnalysisContract,
    aggregate_metrics,
    analyze_result,
    analyze_result_file,
    load_analysis_contract,
    main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def result_fixture(run_id="run-1"):
    return {
        "run_id": run_id,
        "task_id": "synthetic-task",
        "success": False,
        "tests_passed": 4,
        "tests_failed": 0,
        "agent_steps": 10,
        "tool_calls": 9,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "elapsed_seconds": 2.5,
        "failure_type": "max_steps_exhausted",
        "trajectory": [
            {
                "step": 1,
                "action": "list_files",
                "target": None,
                "outcome": "success (3 files)",
            },
            {
                "step": 2,
                "action": "read_file",
                "target": "source.py",
                "outcome": "success",
            },
            {
                "step": 3,
                "action": "read_file",
                "target": "missing.py",
                "outcome": "error: file does not exist: missing.py",
            },
            {
                "step": 4,
                "action": "write_file",
                "target": "notes.txt",
                "outcome": "success",
            },
            {
                "step": 5,
                "action": "run_tests",
                "target": None,
                "outcome": "2 passed / 2 failed",
            },
            {
                "step": 6,
                "action": "write_file",
                "target": "source.py",
                "outcome": "success",
            },
            {
                "step": 7,
                "action": "run_tests",
                "target": None,
                "outcome": "4 passed / 0 failed",
            },
            {
                "step": 8,
                "action": "model_output_error",
                "target": None,
                "outcome": "malformed model output",
            },
            {
                "step": 9,
                "action": "run_command",
                "target": "delete everything",
                "outcome": "error: command is not allowlisted",
            },
            {
                "step": 10,
                "action": "invalid_action",
                "target": None,
                "outcome": "error: unknown action: 'invented'",
            },
        ],
        "trajectory_diagnostics": {"repeated_identical_actions": 1},
    }


def contract():
    return AnalysisContract.from_dict(
        {
            "relevant_source_files": ["source.py"],
            "allowed_output_files": ["source.py"],
            "pristine_tests_passed": 5,
            "pristine_tests_failed": 1,
        }
    )


def test_core_metrics_have_exact_operational_semantics():
    source = result_fixture()
    before = deepcopy(source)

    metrics = analyze_result(source, contract())

    assert source == before
    assert metrics.final_success is False
    assert metrics.final_tests_passed == 4
    assert metrics.final_tests_failed == 0
    assert metrics.test_execution_count == 2
    assert metrics.file_read_count == 1
    assert metrics.file_write_count == 2
    assert metrics.unique_files_read == ["source.py"]
    assert metrics.unique_files_written == ["notes.txt", "source.py"]
    assert metrics.repeated_identical_actions == 1
    assert metrics.max_repeated_action_count == 2
    assert metrics.malformed_model_output_count == 1
    assert metrics.invalid_tool_action_count == 2
    assert metrics.verification_used is True
    assert metrics.revision_after_test_failure is True
    assert metrics.verification_after_revision is True
    assert metrics.max_steps_exhausted is True
    assert metrics.agent_steps == 10
    assert metrics.tool_calls == 9
    assert metrics.input_tokens == 100
    assert metrics.output_tokens == 20
    assert metrics.total_tokens == 120
    assert metrics.elapsed_seconds == 2.5


def test_analysis_contract_metrics_use_exact_declared_paths_and_baseline():
    metrics = analyze_result(result_fixture(), contract())

    assert metrics.analysis_contract_applied is True
    assert metrics.relevant_source_read is True
    assert metrics.relevant_source_write is True
    assert metrics.unexpected_file_created_or_written is True
    assert metrics.passing_test_regression_count == 1

    without_contract = analyze_result(result_fixture())
    assert without_contract.analysis_contract_applied is False
    assert without_contract.relevant_source_read is None
    assert without_contract.relevant_source_write is None
    assert without_contract.unexpected_file_created_or_written is None
    assert without_contract.passing_test_regression_count is None


def test_revision_metrics_require_observed_order_and_explicit_test_failure():
    source = result_fixture()
    source["trajectory"] = [
        {
            "step": 1,
            "action": "write_file",
            "target": "source.py",
            "outcome": "success",
        },
        {
            "step": 2,
            "action": "run_tests",
            "target": None,
            "outcome": "exit 1",
        },
    ]
    source["trajectory_diagnostics"] = {}

    metrics = analyze_result(source)

    assert metrics.verification_used is True
    assert metrics.revision_after_test_failure is False
    assert metrics.verification_after_revision is False


def test_file_counts_exclude_failed_reads_and_writes():
    source = result_fixture()
    source["trajectory"] = [
        {
            "step": 1,
            "action": "read_file",
            "target": "missing.py",
            "outcome": "error: file does not exist: missing.py",
        },
        {
            "step": 2,
            "action": "write_file",
            "target": "source.py",
            "outcome": "error: path escapes the active workspace",
        },
    ]
    source["trajectory_diagnostics"] = {}

    metrics = analyze_result(source)

    assert metrics.file_read_count == 0
    assert metrics.file_write_count == 0
    assert metrics.unique_files_read == []
    assert metrics.unique_files_written == []
    assert metrics.invalid_tool_action_count == 1


def test_aggregate_reports_raw_rates_means_and_medians():
    first = analyze_result(result_fixture(), contract())
    second_source = result_fixture("run-2")
    second_source.update(
        {
            "success": True,
            "tests_passed": 6,
            "tests_failed": 0,
            "agent_steps": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "elapsed_seconds": 1.5,
            "failure_type": None,
            "trajectory": [],
            "trajectory_diagnostics": {},
        }
    )
    second = analyze_result(second_source, contract())

    aggregate = aggregate_metrics([first, second])

    assert aggregate == {
        "number_of_runs": 2,
        "success_rate": 0.5,
        "mean_final_tests_passed": 5.0,
        "median_final_tests_passed": 5.0,
        "mean_final_tests_failed": 0.0,
        "median_final_tests_failed": 0.0,
        "verification_use_rate": 0.5,
        "revision_after_failure_rate": 0.5,
        "verification_after_revision_rate": 0.5,
        "malformed_output_rate": 0.5,
        "invalid_tool_action_rate": 0.5,
        "max_step_exhaustion_rate": 0.5,
        "mean_repeated_identical_actions": 0.5,
        "mean_agent_steps": 5.0,
        "mean_tool_calls": 4.5,
        "mean_input_tokens": 50.0,
        "mean_output_tokens": 10.0,
        "mean_total_tokens": 60.0,
        "mean_elapsed_seconds": 2.0,
        "relevant_source_read_rate": 0.5,
        "relevant_source_write_rate": 0.5,
        "unexpected_file_created_or_written_rate": 0.5,
        "mean_passing_test_regression_count": 0.5,
        "median_passing_test_regression_count": 0.5,
    }


def test_contract_loads_from_future_task_metadata_wrapper(tmp_path):
    path = tmp_path / "task.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "future-task",
                "analysis_contract": {
                    "relevant_source_files": ["src/app.py"],
                    "allowed_output_files": ["src/app.py"],
                    "pristine_tests_passed": 3,
                    "pristine_tests_failed": 2,
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_analysis_contract(path)

    assert loaded.relevant_source_files == frozenset({"src/app.py"})
    assert loaded.allowed_output_files == frozenset({"src/app.py"})
    assert loaded.pristine_tests_passed == 3
    assert loaded.pristine_tests_failed == 2


def test_cli_is_read_only_and_glob_skips_repeat_aggregate(tmp_path, monkeypatch, capsys):
    first = tmp_path / "repeat_condition-run-01.json"
    second = tmp_path / "repeat_condition-run-02.json"
    aggregate = tmp_path / "repeat_condition.json"
    first.write_text(json.dumps(result_fixture("run-1")), encoding="utf-8")
    second.write_text(json.dumps(result_fixture("run-2")), encoding="utf-8")
    aggregate.write_text(json.dumps({"individual_runs": []}), encoding="utf-8")
    before = {path: path.read_bytes() for path in (first, second, aggregate)}
    output = tmp_path / "analysis.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analysis.trajectory_metrics",
            "--glob",
            str(tmp_path / "repeat_condition*.json"),
            "--output",
            str(output),
        ],
    )

    assert main() == 0
    rendered = json.loads(output.read_text(encoding="utf-8"))
    assert rendered["aggregate"]["number_of_runs"] == 2
    assert len(rendered["runs"]) == 2
    assert json.loads(capsys.readouterr().out) == rendered
    assert all(path.read_bytes() == content for path, content in before.items())


def test_representative_existing_result_schema_parses_read_only():
    path = REPO_ROOT / "results" / "task06_retry_idempotency-4a67af377dc7.json"
    before = path.read_bytes()

    metrics = analyze_result_file(path)

    assert metrics.task_id == "task06_retry_idempotency"
    assert metrics.final_success is True
    assert metrics.final_tests_passed == 6
    assert metrics.test_execution_count == 2
    assert metrics.revision_after_test_failure is True
    assert metrics.verification_after_revision is True
    assert path.read_bytes() == before


@pytest.mark.parametrize("field", ["tests_passed", "total_tokens", "elapsed_seconds"])
def test_invalid_result_values_are_rejected(field):
    source = result_fixture()
    source[field] = -1

    with pytest.raises(ValueError, match=field):
        analyze_result(source)
