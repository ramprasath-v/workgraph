# Frozen cross-family research checkpoint

## Scope and evidence policy

This checkpoint was defined after WorkGraph Families 1–3 and before any Family 4
task or policy implementation. It is deterministic and offline. The machine-readable
checkpoint is generated from the explicit mappings in
`analysis/cross_family_manifest.json`; condition identity is never inferred from a
filename.

The evidence boundary is important:

- Family 3 retains each Task 09 aggregate and all five raw run JSON files for all
  five conditions. Its numerical, efficiency, and trajectory claims below are
  machine-derived from those files.
- The original Task 04 and Task 07 Kaggle per-run results were not retained. The
  repository retains their tasks and assistance artifacts, but not the benchmark
  evidence needed to recompute outcomes. Families 1 and 2 therefore have no
  numerical or trajectory metrics in this checkpoint.
- The Family 1 and Family 2 outcome-class labels are frozen historical research
  observations, not claims re-derived by this utility. They must not be used as if
  they had the same evidentiary status as Family 3.
- Missing measurements are represented as `null`; none are reconstructed from
  narrative reports.

## Cross-family summary

| Family | Consumer task | Outcome class | Retained benchmark evidence | Machine-derived checkpoint result |
| --- | --- | --- | --- | --- |
| 1 — resource/path transfer | Task 04 | A. Capability-enabling assistance | Original raw results not retained | Unavailable; historical classification only |
| 2 — retry/idempotency | Task 07 | B. Assistance insufficient | Original raw results not retained | Unavailable; historical classification only |
| 3 — state/cache consistency | Task 09 | C. Assistance-induced interference | Five aggregates and 25 raw runs retained | Baseline 5/5; every tested assistance condition 0/5 |

These are observed outcome classes in the current experiments, not universal laws.
In particular, the first two rows are qualitative project-history classifications
with an explicit evidence-retention limitation.

## Family 3 outcome and inference accounting

“Qwen-only” fields include only the downstream fixer. Total-inference fields use
the accounting persisted by the repeated-run harness. For scout conditions, the
average total-inference value represents per-deployment accounting, while the
frozen-experiment total counts the one scout acquisition once across the five-run
experiment.

| Condition | Success | Mean Qwen input / output / total tokens | Mean Qwen elapsed (s) | Mean total-inference tokens / elapsed (s) | Frozen experiment total tokens / elapsed (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline / no context | 5/5 (100%) | 4,978 / 532 / 5,510 | 106.099110 | 5,510 / 106.099110 | 27,550 / 530.495552 |
| Relevant Task 08 transfer | 0/5 (0%) | 9,303.6 / 1,148.6 / 10,452.2 | 166.599470 | 10,452.2 / 166.599470 | 52,261 / 832.997349 |
| Irrelevant Task 05 transfer | 0/5 (0%) | 5,878 / 621 / 6,499 | 152.373046 | 6,499 / 152.373046 | 32,495 / 761.865229 |
| Detailed current-task scout | 0/5 (0%) | 11,544 / 825 / 12,369 | 173.820434 | 24,557 / 196.241585 | 74,033 / 891.523319 |
| Compact current-task scout | 0/5 (0%) | 4,954 / 545 / 5,499 | 196.846947 | 17,687 / 219.268098 | 39,683 / 1,006.655888 |

## Family 3 trajectory measurements

Task 09’s `analysis_contract` was declared before model exposure. It permits exact
measurement of relevant-source access, unexpected writes, and regression from the
pristine four-passing-test state. Rates are run-level fractions across five runs.

| Condition | Mean final pass / fail | Mean steps / calls | Verify rate | Malformed rate | Invalid-action rate | Max-step rate | Mean repeats | Relevant read / write rate | Unexpected-write rate | Mean passing-test regression |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 6 / 0 | 8 / 6 | 100% | 100% | 100% | 0% | 1 | 100% / 100% | 0% | 0 |
| Relevant transfer | 0 / 1 | 8 / 7 | 100% | 100% | 0% | 100% | 1 | 100% / 100% | 100% | 4 |
| Irrelevant transfer | 4 / 2 | 8 / 6 | 100% | 100% | 100% | 100% | 1 | 100% / 100% | 0% | 0 |
| Detailed scout | 0 / 6 | 7 / 5 | 100% | 100% | 0% | 0% | 2 | 0% / 100% | 0% | 4 |
| Compact scout | 0 / 6 | 8 / 5 | 0% | 100% | 100% | 100% | 2 | 100% / 100% | 0% | 4 |

Operational definitions are inherited unchanged from
`docs/trajectory-measurement.md`. A relevant write is not evidence of a correct
write, and malformed or invalid actions can coexist with eventual success.

## Interpretation

The strongest supported claim is narrow: for Task 09 with
`Qwen/Qwen2.5-7B-Instruct`, this harness, and an eight-step budget, the unaided
condition succeeded in all five retained runs while each of four assistance
conditions succeeded in zero of five. Relevant Task 08 transfer was therefore not
merely insufficient in this setting; its condition-level outcome was worse than
no assistance, and its trajectories showed a four-test mean regression plus
unexpected writes in every run.

The retained evidence also distinguishes failure modes. Irrelevant transfer kept
the pristine four passing tests on average, whereas relevant transfer and both
scout representations regressed them. The detailed scout did not exhaust the
recorded step budget but still ended with all six tests failing. The compact scout
never invoked verification in any retained run.

This evidence falsifies the naive hypothesis, for this model/harness/task setting:

> If retrieved guidance is relevant and correct, injecting it cannot hurt.

It does not establish that assistance is generally harmful, that one representation
is universally superior, that the same outcomes hold for another model, or that a
routing policy will outperform fixed strategies. With five runs per retained
condition, this checkpoint also makes no population-level significance claim.

## Predeclared Next Hypothesis

Verified experience should not be injected unconditionally. The utility of
assistance depends on the target model's unaided capability, the task, and the
representation of the retrieved experience.

The next WorkGraph system hypothesis is:

> A policy that decides whether to use no assistance, historical verified
> experience, current-task scouting, or model escalation can outperform
> unconditional experience injection in reliability and/or resource efficiency.

This hypothesis is recorded before Family 4 design, implementation, or observation.

## Proposed Family 4 decision-policy experiment — not implemented

Family 4 should evaluate a frozen policy with four candidate actions:

1. no assistance;
2. historical verified transfer;
3. compact current-task scout; or
4. escalate to a stronger model.

The policy must commit to its action before the target run and before deterministic
evaluation. It must not see a solution, producer patch, hidden evaluator result,
post-run outcome, or future trajectory.

Legally observable pre-execution signals may include, if predeclared:

- public task description, language, and declared environment;
- read-only structural workspace facts such as file count and language mix;
- target model identity and capability tier established independently of the
  current task;
- assistance provenance, verification status, representation type, and size;
- source/target similarity computed only from public task descriptions and the
  portable abstraction, never the producer patch;
- estimated context, inference-token, latency, and escalation costs; and
- whether a candidate artifact passes deterministic schema and leakage checks.

Family 4 should use held-out tasks and freeze the policy, thresholds, primary
reliability metric, resource metrics, and tie-breaking rules before any target
outcomes are observed. It should compare the policy with each fixed action, report
interference rate and resource use separately, and may calculate a retrospective
oracle only as a labeled upper bound—not as a policy input. Public or hidden tests,
target-run failures, and post-run trajectories must never become routing features.

No Family 4 task, router, threshold, model-selection implementation, or experiment
is created by this checkpoint.

## Reproduction

```bash
python3 -m analysis.cross_family_checkpoint \
  --manifest analysis/cross_family_manifest.json \
  --output analysis/cross_family_checkpoint.json
```

The generated JSON includes every explicit evidence path and SHA-256 digest. The
builder verifies aggregate/raw identity and accounting consistency before emitting
the checkpoint.
