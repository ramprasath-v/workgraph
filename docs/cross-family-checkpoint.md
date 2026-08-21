# Cross-family retained-evidence checkpoint

## Evidence boundary

This checkpoint is deterministic and offline. The original Task 04 and Task 07
Kaggle runs remain unavailable and are not reconstructed. Families 1 and 2 now
have separately versioned retained-evidence reproductions; Family 3 retains its
original five-condition Task 09 evidence. The machine-readable sources are
`analysis/cross_family_manifest.json`, the two reproduction evidence manifests,
and `analysis/cross_family_checkpoint.json`.

## Exact retained outcomes

| Family | Evidence | Baseline | Relevant transfer | Classification / interpretation |
| --- | --- | ---: | ---: | --- |
| 1 — Task 04 | New reproduction | 0/5 | 5/5 | `FULL_REPRODUCTION`; no trajectory wrote the test file |
| 2 — Task 07 | New reproduction | 0/5 | 5/5 harness-recorded | `NON_REPRODUCTION` of the historical 0/5→0/5 pattern; all assisted runs rewrote the test file and ended with only 1 passing test |
| 3 — Task 09 | Original retained experiment | 5/5 | 0/5 | Assistance interference observed; mechanism unresolved |

Family 3's irrelevant-transfer, detailed-scout, and compact-scout conditions also
remain 0/5. Family 2's 5/5 is an exact report of the persisted harness `success`
field, not evidence that the pristine six-test suite passed. The original Family 2
historical observation and the new reproduction are distinct records.

## Reproduction trajectory measurements

All values below come from the frozen `analysis.trajectory_metrics` analyzer.
Family 1 and Task 07 have no predeclared `analysis_contract`, so an
“unexpected-write rate” is not manufactured for them.

| Condition | Final pass/fail | Steps/calls | Verify | Revise after failure | Max-step | Malformed | Invalid action | Repeats | Input/output/total tokens | Elapsed (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F1 baseline | 2.2 / 2.8 | 8 / 6 | 100% | 100% | 0% | 100% | 100% | 0 | 5,976 / 544 / 6,520 | 412.668231 |
| F1 relevant | 5 / 0 | 6 / 4 | 100% | 0% | 0% | 100% | 0% | 0 | 3,393 / 309 / 3,702 | 237.298690 |
| F2 baseline | 4 / 2 | 2 / 0 | 0% | 0% | 0% | 100% | 0% | 0 | 253 / 15 / 268 | 47.897673 |
| F2 relevant | 1 / 0 | 8 / 6 | 100% | 100% | 0% | 100% | 0% | 1 | 7,280 / 549 / 7,829 | 413.976860 |

F1 baseline read `report_renderer/loader.py` and wrote it plus
`report_renderer/renderer.py`; F1 relevant read and wrote only the loader. F2
baseline read and wrote no files. F2 relevant read `delivery_receiver.py` and
wrote both it and `test_delivery_receiver.py` in all five runs.

## Strongest supported claim

> Verified external assistance can enable a consumer that fails unaided, while
> assistance injection can also interfere with a consumer that succeeds unaided;
> assistance utility is conditional rather than monotonic.

Family 1 supplies the new retained enabling contrast. Family 3 supplies the
retained interference contrast. This does not establish a general benefit or harm,
prove model capability as causal, prove semantic negative transfer, validate the
routing policy, or support broad generalization. Family 3's mechanism remains
unresolved: wrapper structure, context length, authoritative framing, placement,
and token/latency effects remain alternative explanations.

## Minimum next Task 09 mechanism ablation — recommendation only

Reuse the already-retained baseline and authoritative relevant-transfer conditions
as anchors. Preregister three new conditions under the same frozen task, model,
budget, generation settings, repetitions, and evaluator:

1. **Empty assistance wrapper:** identical injection template with no knowledge.
2. **Neutral length-matched context:** non-directive, task-irrelevant text matched
   approximately to the relevant context's size in the same wrapper and position.
3. **Unframed relevant principle:** the same relevant portable principle without
   “verified,” “prior experience,” or other authority framing, in the same position.

Baseline versus empty tests wrapper effects; empty versus neutral tests context
load/length effects; neutral versus unframed relevant tests semantic content absent
authority; unframed versus the retained authoritative condition tests authority
framing. Placement variation should follow only if these minimum controls leave a
placement ambiguity. Nothing in this checkpoint executes or implements the ablation.

## Reproduction

```bash
python3 -m analysis.cross_family_checkpoint \
  --manifest analysis/cross_family_manifest.json \
  --output analysis/cross_family_checkpoint.json
```
