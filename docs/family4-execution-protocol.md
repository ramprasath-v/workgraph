# Family 4 frozen execution protocol

This protocol was frozen before any Family 4 scout or target-model execution. The
authoritative machine-readable artifact is
`preregistrations/family4_execution_manifest_v0_1.json`.

## Models and budgets

- Task 10 target: Vertex `gemini-2.5-flash`, high tier.
- Tasks 11 and 12 target: Transformers `Qwen/Qwen2.5-7B-Instruct`, standard tier.
- Escalation: Vertex `gemini-2.5-pro`, directly from pristine state, no assistance
  artifact and no preceding target attempt.
- Every unique run set uses five repetitions and eight agent steps.

Transformers uses `temperature=0`, `do_sample=false`, and
`max_new_tokens=512`; `top_p`, `top_k`, and seed are not passed. Vertex sends
`temperature=0`; `top_p`, `top_k`, and seed remain omitted provider defaults.

## Historical-transfer assignments

Tasks 10 and 12 score all four pre-Family-4 transfers using the frozen Policy v0.1
public lexical-overlap function, select the largest score, and break ties by
transfer ID. Task 11 retains the candidate frozen in its earlier preregistration.
Qualification is irrelevant to the unconditional comparison arm.

- Task 10: `transfer_56c07e702add42b7a04b9c7f7a4a7230`, score `0.238095`.
- Task 11: `transfer_93a42588ddd62085a6289d9b12613079`, score `0.086957`.
- Task 12: `transfer_56c07e702add42b7a04b9c7f7a4a7230`, score `0.190476`.

## Scout and compact protocols

Acquire exactly one read-only Vertex `gemini-2.5-flash` scout per task, in task
order. It may use `list_files`, `read_file`, and `run_tests` only within a fresh
copy of the public task workspace. It receives no analysis contract, historical
transfer, target outcome, prior trajectory, expected patch, corrected source, or
unrelated repository content.

After all three scouts are frozen, compile in task order with
`family4-generic-0.1`. Compilation is deterministic and has zero inference cost.
Only observations, suspected area, recommended investigation, and constraints may
inform guidance. The compiler excludes code/diffs and redacts filenames, paths,
identifiers, source expressions, and test identifiers while retaining source-scout
and acquisition provenance.

## Strategy aliases

| Task | Policy v0.1 | No assistance | Historical | Compact scout | Escalate |
|---|---|---|---|---|---|
| Task 10 | `task10_no_assistance` | same | `task10_historical_transfer` | `task10_compact_scout` | `task10_escalate` |
| Task 11 | `task11_no_assistance` | same | `task11_historical_transfer` | `task11_compact_scout` | `task11_escalate` |
| Task 12 | `task12_escalate` | `task12_no_assistance` | `task12_historical_transfer` | `task12_compact_scout` | same as policy |

Each unique run set executes once. Aliased strategy labels reference the same five
runs and are not independent evidence. Every run resets from and verifies the exact
frozen pristine task hash.

## Accounting and metrics

Target, scout, and escalation input/output/provider-total tokens and elapsed times
are reported separately. Strategy totals include every inference component. A scout
reused over five repetitions is reported both as one acquisition plus five target
runs and as one acquisition plus one target run for new-task deployment.
Deterministic compaction costs zero inference; artifact size and estimated prompt
tokens are separate.

Frozen metrics include verified success, successes/repetitions, target and total
inference tokens, elapsed time, escalation and verification-use rates, max-step
exhaustion, malformed output, invalid tool actions, relevant reads/writes,
unexpected writes, passing-test regressions, and cost per verified success. Cost per
success is `null` when success count is zero. Results are descriptive; no
significance claim is made from five repetitions.

Execution order is: acquire Task 10–12 scouts; compile Task 10–12 compact scouts;
then execute the twelve unique run sets in the exact order recorded in the manifest.
No intermediate outcome may change later execution.
