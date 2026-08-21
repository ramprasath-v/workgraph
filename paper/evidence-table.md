# Cross-family evidence table

## Central retained evidence

| Family | Consumer | Baseline | Relevant transfer | Other retained conditions | Evidence status | Interpretation |
| --- | --- | ---: | ---: | --- | --- | --- |
| 1 — resource/path | Task 04, Qwen 2.5 7B | 0/5 | 5/5 | Original other conditions unavailable | New core reproduction; raw per-run evidence retained: **yes** | Clean enabling contrast; full frozen rule reproduction |
| 2 — retry/idempotency | Task 07, Qwen 2.5 7B | 0/5 | 5/5 harness-recorded | Original other conditions unavailable | New core reproduction; raw per-run evidence retained: **yes** | Historical 0/5→0/5 did not reproduce; assisted runs rewrote tests and finished at 1 passing test |
| 3 — state consistency | Task 09, Qwen 2.5 7B | 5/5 | 0/5 | Irrelevant 0/5; detailed scout 0/5; compact scout 0/5 | Original experiment; raw per-run evidence retained: **yes** | Assistance interference in this task/model/harness setting; mechanism unresolved |

The original Task 04/07 evidence remains unretained. The new reproductions are
separate evidence and do not retroactively restore it. Family 2's persisted success
count is not treated as pristine-suite verification because all five assisted
trajectories wrote `test_delivery_receiver.py` and the final record contains only
`1 passed / 0 failed`.

## Reproduction trajectory comparison

| Condition | Success | Mean tests pass/fail | Steps/calls | Verify/revise | Malformed/invalid | Tokens (in/out/total) | Elapsed (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F1 baseline | 0/5 | 2.2 / 2.8 | 8 / 6 | 100% / 100% | 100% / 100% | 5,976 / 544 / 6,520 | 412.668231 |
| F1 relevant | 5/5 | 5 / 0 | 6 / 4 | 100% / 0% | 100% / 0% | 3,393 / 309 / 3,702 | 237.298690 |
| F2 baseline | 0/5 | 4 / 2 | 2 / 0 | 0% / 0% | 100% / 0% | 253 / 15 / 268 | 47.897673 |
| F2 relevant | 5/5 recorded | 1 / 0 | 8 / 6 | 100% / 100% | 100% / 0% | 7,280 / 549 / 7,829 | 413.976860 |

## Family 3 anchors

The retained Task 09 condition outcomes remain: baseline **5/5**, relevant
transfer **0/5**, irrelevant transfer **0/5**, detailed scout **0/5**, and compact
scout **0/5**. Existing aggregate/run hashes and contract-aware trajectory metrics
remain in `analysis/cross_family_checkpoint.json` and are unchanged as inputs.

These deterministic repetitions are robustness checks, not independent samples or
population-level statistical evidence.
