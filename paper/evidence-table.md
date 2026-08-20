# Cross-family evidence table

## Evidence boundary

Family 3 values below come from the frozen machine-readable checkpoint, which was
validated against five aggregates and 25 retained raw Task 09 run files. Families 1
and 2 have no retained original Kaggle run files; their entries are historical
project observations and are neither reconstructed nor assigned machine-derived
trajectory values. The deterministic projection is `paper/evidence-summary.json`.

## Central evidence table

| Family | Consumer task | Model | Baseline success | Relevant historical | Irrelevant historical | Detailed scout | Compact scout | Evidence status | Primary interpretation |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 — resource/path | Task 04 | Qwen 2.5 7B | 0/5, historical record only | 5/5, historical record only | Not recomputable | Not recomputable | Success reported; count not recomputable | Historical observation; raw per-run evidence retained: **no** | Assistance associated with capability-enabling behavior; numerical reproducibility unavailable |
| 2 — retry/idempotency | Task 07 | Qwen 2.5 7B | Failure reported; count not recomputable | Failure reported; count not recomputable | Failure reported; count not recomputable | Not recomputable | Not recomputable | Historical observation; raw per-run evidence retained: **no** | Assistance remained insufficient; recorded behavior differed, but machine trajectory claims are unavailable |
| 3 — state consistency | Task 09 | Qwen 2.5 7B | **5/5** | **0/5** | **0/5** | **0/5** | **0/5** | Machine-derived; five aggregates and 25 raw runs retained: **yes** | Assistance-induced interference in this task/model/harness setting |

The Family 1 0-to-5 statement is retained only because the frozen historical record
describes it; it is not machine-recomputed. Missing Family 1/2 cells are not inferred
from narrative trajectory descriptions.

## Family 3 inference accounting

Target tokens are downstream Qwen tokens. Total-inference values include scout
acquisition where applicable. Frozen experiment totals count the shared scout once.

| Condition | Success | Mean target input / output / total | Mean target elapsed (s) | Mean total-inference tokens / elapsed (s) | Frozen experiment total tokens / elapsed (s) |
|---|---:|---:|---:|---:|---:|
| Baseline | 5/5 | 4,978 / 532 / 5,510 | 106.099110 | 5,510 / 106.099110 | 27,550 / 530.495552 |
| Relevant transfer | 0/5 | 9,303.6 / 1,148.6 / 10,452.2 | 166.599470 | 10,452.2 / 166.599470 | 52,261 / 832.997349 |
| Irrelevant transfer | 0/5 | 5,878 / 621 / 6,499 | 152.373046 | 6,499 / 152.373046 | 32,495 / 761.865229 |
| Detailed scout | 0/5 | 11,544 / 825 / 12,369 | 173.820434 | 24,557 / 196.241585 | 74,033 / 891.523319 |
| Compact scout | 0/5 | 4,954 / 545 / 5,499 | 196.846947 | 17,687 / 219.268098 | 39,683 / 1,006.655888 |

The detailed/compact scout acquisition record reports 9,525 input, 570 output,
12,188 provider-total tokens, and 22.421151 seconds. Provider-total tokens need not
equal input plus output because provider accounting can include additional token
categories.

## Family 3 behavioral metrics

Rates are run-level fractions over five runs. “Malformed” and “invalid” use the
frozen operational definitions and can coexist with eventual success. Reads/writes
measure observable tool use, not semantic understanding.

| Condition | Final pass/fail | Max-step | Unexpected write | Passing-test regression | Relevant read/write | Verification | Invalid action | Mean steps/calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 6 / 0 | 0% | 0% | 0 | 100% / 100% | 100% | 100% | 8 / 6 |
| Relevant transfer | 0 / 1 | 100% | 100% | 4 | 100% / 100% | 100% | 0% | 8 / 7 |
| Irrelevant transfer | 4 / 2 | 100% | 0% | 0 | 100% / 100% | 100% | 100% | 8 / 6 |
| Detailed scout | 0 / 6 | 0% | 0% | 4 | 0% / 100% | 100% | 0% | 7 / 5 |
| Compact scout | 0 / 6 | 100% | 0% | 4 | 100% / 100% | 0% | 100% | 8 / 5 |

All five conditions have a malformed-output run rate of 100% under the persisted
definition. The relevant-transfer condition revised and reverified after quantified
test failure in every run. Detailed scout also recorded revision and reverification
in every run. These behaviors did not produce verified success.

## Interpretation discipline

- Family 3 falsifies, for this setting, the naive claim that relevant correct
  guidance cannot hurt.
- It does not show that assistance generally hurts.
- Differences among failed trajectories are descriptive; they do not establish
  reasoning quality.
- Five deterministic or near-deterministic repetitions are not five independent
  population samples.
