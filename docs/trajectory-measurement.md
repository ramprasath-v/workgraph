# Predeclared trajectory measurement framework

## Purpose and freeze point

Binary task success is necessary but insufficient for analyzing coding-agent
behavior. Two unsuccessful runs can differ observably: one may never inspect the
workspace, while another may read application code, edit it, run tests, respond to
a failure, and verify a revision. These observations do not turn failure into
success, but recording them prevents binary outcomes from erasing behavioral
differences.

This framework is defined and tested after experimental Families 1 and 2 and
before Family 3. Its definitions are frozen for prospective Family 3 analysis.
It is an offline consumer of completed result JSON. It does not participate in
inference, change prompts or tools, or affect benchmark outcomes.

## Core operational definitions

All trajectory positions below use the persisted trajectory order. A successful
file action has an outcome string beginning with `success`. A failed file action
is not counted as a successful read or write.

| Metric | Deterministic definition |
| --- | --- |
| `final_success` | Persisted deterministic `success` boolean. |
| `final_tests_passed` | Persisted final `tests_passed`. |
| `final_tests_failed` | Persisted final `tests_failed`. |
| `test_execution_count` | Number of trajectory actions named `run_tests`, regardless of their result. |
| `file_read_count` | Number of successful `read_file` actions. |
| `file_write_count` | Number of successful `write_file` actions. |
| `unique_files_read` | Sorted unique targets of successful `read_file` actions. |
| `unique_files_written` | Sorted unique targets of successful `write_file` actions. |
| `repeated_identical_actions` | Existing non-negative trajectory diagnostic when present; otherwise the sum of occurrences beyond the first for each exact `(action, target)` pair. |
| `max_repeated_action_count` | Largest occurrence count for any exact `(action, target)` pair; zero for an empty trajectory. |
| `malformed_model_output_count` | Count of `model_output_error` entries or outcomes explicitly containing `malformed model output`. |
| `invalid_tool_action_count` | Count of `invalid_action` entries and tool-error outcomes matching predeclared validation/safety failures: invalid fields, unknown actions, unsafe or non-allowlisted commands, absolute/escaping/empty paths, invalid command shapes, or non-string content. Runtime errors such as a missing file are excluded. |
| `verification_used` | At least one `run_tests` action occurred. |
| `revision_after_test_failure` | A `run_tests` outcome explicitly reported a positive failed-test count, followed later by a successful `write_file`. An unquantified `exit 1` is insufficient evidence. |
| `verification_after_revision` | `revision_after_test_failure` occurred and a later `run_tests` action followed the qualifying revision. |
| `max_steps_exhausted` | Persisted `failure_type` equals `max_steps_exhausted`. It is not inferred from step count alone. |
| `agent_steps` | Persisted agent step count. |
| `tool_calls` | Persisted tool-call count. |
| `input_tokens` | Persisted fixer input-token count. |
| `output_tokens` | Persisted fixer output-token count. |
| `total_tokens` | Persisted fixer provider-total token count. |
| `elapsed_seconds` | Persisted fixer elapsed time. |

## Optional predeclared task semantics

Future `task.json` files may declare an `analysis_contract` before any benchmark
result is observed:

```json
{
  "analysis_contract": {
    "relevant_source_files": ["src/application.py"],
    "allowed_output_files": ["src/application.py"],
    "pristine_tests_passed": 3,
    "pristine_tests_failed": 2
  }
}
```

The analyzer applies only the fields explicitly present:

- `relevant_source_read`: at least one successful `read_file` target exactly
  equals a path in `relevant_source_files`.
- `relevant_source_write`: at least one successful `write_file` target exactly
  equals a path in `relevant_source_files`.
- `unexpected_file_created_or_written`: at least one successful `write_file`
  target is absent from `allowed_output_files`. The trajectory cannot distinguish
  creation from replacement, hence the explicit combined name.
- `passing_test_regression_count`: `max(0, pristine_tests_passed -
  final_tests_passed)`.

Tasks 01–07 are not retroactively annotated. Adding semantic contracts after
observing their results would introduce post-hoc researcher judgment. Their core
metrics remain analyzable; contract-dependent metrics are `null`.

## Condition aggregation

For multiple run results from one condition, the analyzer reports run count,
success rate, mean and median final test counts, run-level rates for verification,
revision, re-verification, malformed output, invalid tool actions, and max-step
exhaustion, plus means for repetition, steps, calls, tokens, and elapsed time.

Malformed-output and invalid-tool-action rates are the fraction of runs with at
least one such event, not the average number of events. When a contract field is
present for every analyzed run, corresponding semantic rates and test-regression
mean/median are also reported.

No statistical significance test is performed at this stage.

## No composite quality score

The framework intentionally defines no weighted “agent quality,” “grounding,” or
behavioral score. Weight selection would embed undeclared value judgments and can
hide tradeoffs among interpretable observations. Raw measures remain separate.

## Limitations and interpretation

- Trajectory actions measure observable behavior, not hidden reasoning.
- Reading or writing a file does not prove semantic understanding.
- More steps, file operations, or test runs are not inherently better.
- Concise persisted outcomes may omit evidence available in raw provider logs;
  the analyzer does not reconstruct missing evidence.
- Behavioral improvement without final deterministic success must not be
  described as capability displacement.

## Read-only CLI

Analyze explicit completed run files:

```bash
python3 -m analysis.trajectory_metrics \
  results/condition-run-01.json \
  results/condition-run-02.json
```

Analyze per-run files selected by a repeat glob (matching aggregate summaries are
ignored because they are not completed run artifacts):

```bash
python3 -m analysis.trajectory_metrics \
  --glob "results/repeat_condition_*.json"
```

For a future predeclared task contract:

```bash
python3 -m analysis.trajectory_metrics \
  --task-metadata tasks/future_task/task.json \
  --glob "results/repeat_future_task_*-run-*.json"
```

`--output analysis/result.json` may write a separate analysis artifact. The CLI
refuses to overwrite an input result JSON.
