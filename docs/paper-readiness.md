# WorkGraph paper-readiness review

## Bottom line

WorkGraph is ready for a rigorous internal report and is closer to a transparent
technical report. It is still not ready for a strong general conference claim.
The evidence asymmetry improved: Family 1 now has a clean retained reproduction of
an enabling contrast, and Family 3 retains an interference contrast. Family 2's
new reproduction did not reproduce its historical pattern and uncovered a serious
verification-integrity threat because assisted runs changed the test file.

## Strongest supported claim

> Verified external assistance can enable a consumer that fails unaided, while
> assistance injection can also interfere with a consumer that succeeds unaided;
> assistance utility is conditional rather than monotonic.

This is a conditional observation across the retained Task 04 and Task 09 settings,
not a universal memory result. The mechanism behind Family 3 is unresolved.
Prompt-wrapper structure, context length, placement, authority framing, and token or
latency effects are live alternatives requiring ablation.

## Evidence status

- **Family 1:** new retained reproduction, baseline 0/5 and relevant transfer 5/5;
  `FULL_REPRODUCTION` under its frozen rule. No run wrote the test file.
- **Family 2:** new retained reproduction, baseline 0/5 and harness-recorded
  relevant transfer 5/5; `NON_REPRODUCTION` of the historical 0/5→0/5 pattern.
  Every assisted run rewrote the test file and ended with one passing test, so this
  is not evidence of full pristine-suite verification.
- **Family 3:** original retained Task 09 evidence remains baseline 5/5 and all four
  assistance conditions 0/5. The interference outcome is measurable; its causal
  mechanism is not isolated.

The original Task 04 and Task 07 raw runs were never retained. The new versioned
reproductions do not reconstruct or replace those historical records.

## Claims not supported

The evidence does not support claims that:

- external memory generally helps or generally hurts;
- consumer capability level is proven causal;
- Family 3 proves semantic negative transfer;
- prompt length, wrapper, authority, or placement have been ruled out;
- Family 2's assisted runs passed the pristine task suite;
- Policy v0.1 or routing works;
- results generalize broadly across tasks, models, or agent harnesses;
- five deterministic repetitions are statistically independent; or
- file reads and writes reveal hidden reasoning or semantic understanding.

## Minimum next mechanism experiment

Before Family 4, preregister the smallest Task 09 ablation that reuses the retained
baseline and authoritative relevant-transfer anchors and adds only:

1. an empty assistance wrapper;
2. neutral approximately length-matched context in the same wrapper and position;
3. the same relevant principle without verified/prior-experience authority framing.

Keep the frozen Task 09, Qwen model, generation settings, max steps, repetitions,
tools, and evaluator unchanged. These conditions separate wrapper, context-load,
semantic-content, and authority-framing explanations with the fewest new runs.
Placement variation is the next follow-up only if ambiguity remains.

## Paper-readiness change

- **Internal research note:** ready, with the Family 2 integrity finding prominent.
- **Technical report/preprint:** conditionally ready after the minimum Task 09
  ablation and complete related-work positioning.
- **Workshop paper:** closer, but still needs the mechanism ablation and preferably
  a closest memory/skill baseline or additional consumer model.
- **Full conference paper:** not ready; task/model breadth, causal ablations,
  baselines, uncertainty design, and external validity remain insufficient.

Family 4 and Policy v0.1 remain frozen and unexecuted. They cannot resolve the
Family 3 mechanism question and were not changed during this offline update.
