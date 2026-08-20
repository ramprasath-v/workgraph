# WorkGraph paper-readiness review

## Bottom line

WorkGraph is ready as a rigorous internal research note and conditionally ready for
a transparent technical report. It is not yet supported as a full conference paper.
The strongest current contribution is not “experience improves agents,” but a
controlled demonstration that assistance was non-monotonic across the observed
settings. Two of the three regimes remain historical observations without original
raw evidence; only Family 3 supports machine-derived numerical and trajectory claims.

Recommended working title:

> **When Agent Experience Helps, Fails, and Hurts: Conditional Assistance in
> Tool-Using Language-Model Agents**

This broader title fits the cross-family evidence better than treating capability
displacement as the sole or universal mechanism.

Working materials:

- [`paper/outline.md`](../paper/outline.md): full paper skeleton, abstract, RQs,
  definitions, positioning, limitations, and proposed figures.
- [`paper/evidence-table.md`](../paper/evidence-table.md): central cross-family and
  Family 3 numerical tables.
- [`paper/reviewer-risks.md`](../paper/reviewer-risks.md): risks, experiment ranking,
  publication readiness, and scorecard.
- [`paper/evidence-summary.json`](../paper/evidence-summary.json): deterministic
  provenance-preserving projection of the frozen checkpoint.

## Abstract draft

Tool-using language-model agents can receive prior verified experience, distilled
transfer knowledge, or current-task scouting, but injecting more relevant context
need not improve execution. We present WorkGraph, an experimental harness that
captures successful executions as verification-backed artifacts and measures how
different assistance representations affect a downstream coding agent. Across three
small, hand-built task families using Qwen 2.5 7B as the principal consumer, the
frozen project record contains three qualitatively different regimes. Family 1 is a
historical observation in which relevant assistance was associated with a change
from zero to five successful runs and capability-enabling behavior; its original
per-run Kaggle evidence was not retained, so this result is not machine-recomputed.
Family 2 is a historical observation in which assistance remained insufficient,
although recorded trajectories differed; its original raw evidence is likewise
unavailable. Family 3 retains complete raw evidence: on Task 09, unaided Qwen
succeeded in 5/5 runs, whereas relevant historical transfer, irrelevant historical
transfer, a detailed current-task scout, and a compact scout each succeeded in 0/5.
The retained trajectories show representation-dependent regressions, unexpected
writes, verification behavior, and inference costs, but do not establish hidden
reasoning quality. These controlled cases show that external assistance was not
monotonically beneficial in this harness. They do not establish population-level
generalization. We preregistered a deterministic policy that selects no assistance,
historical transfer, compact scouting, or escalation, together with a held-out
Family 4 protocol; that policy has not yet been evaluated.

## Research questions

1. Can verified prior experience enable a target model that fails unaided?
2. When does assistance fail to overcome consumer execution limitations?
3. Can relevant assistance interfere with a model that succeeds unaided?
4. How do assistance representations change observable behavior and inference cost?
5. Can a leakage-free pre-execution policy select assistance, scouting, unaided
   execution, or escalation? **Not evaluated; Family 4 remains unrun.**

## Strongest supported claim

> In these controlled tool-using-agent experiments, external assistance was not
> monotonically beneficial. Depending on the task/model setting, assistance was
> observed to enable success, fail to overcome execution limitations, or interfere
> with an agent that succeeded unaided.

The enabling and insufficient regimes are historical project observations whose raw
runs were not retained. The interference result is machine-derived for Task 09,
Qwen 2.5 7B, this harness, and an eight-step budget. This division must remain visible
in the abstract, results, figures, captions, and conclusion.

## Claims not supported

The current evidence must not be used to claim that:

- verified experience generally reduces required model size;
- assistance generally helps or generally hurts;
- compact representation is universally superior;
- Policy v0.1 works;
- WorkGraph routing improves expected cost;
- effects generalize beyond current tasks, Qwen 7B, or this harness;
- five repetitions provide population-level statistical evidence;
- deterministic repeated generations are statistically independent;
- file reads/writes prove reasoning quality;
- Family 1/2 results are reproducible from retained raw evidence;
- the observed interference has been isolated from prompt length, placement, or
  schema interactions; or
- WorkGraph’s memory, skill synthesis, scouting, or routing components are themselves
  novel.

## Family 4 status

- Policy v0.1 was frozen before Family 4 task creation.
- Tasks 10–12 and their hashes are frozen.
- Decisions are preregistered: Task 10 `NO_ASSISTANCE`, Task 11 `NO_ASSISTANCE`,
  Task 12 `ESCALATE`.
- The execution manifest, transfer assignments, scout protocol, compact compiler,
  model assignments, aliases, budgets, metrics, and order are frozen.
- No Family 4 scout, compact artifact, model execution, or result exists.

Family 4 is therefore a ready-to-run held-out policy validation set. This prospective
discipline is valuable even if execution follows the first paper draft.

## Family 4 go/no-go

**Do not make Family 4 the immediate first experiment.** Begin drafting now, then
restore Family 1/2 raw evidence and run prompt/context ablations. Family 4 should be
run next under its unchanged manifest because it directly evaluates RQ5, but it
cannot repair missing evidence for RQ1/RQ2 or rule out the main alternative
explanation for Family 3.

## Publication readiness

- **Internal note:** ready.
- **Technical report/preprint:** conditional; acceptable only with prominent limits,
  completed related-work citations, and preferably restored Family 1/2 evidence.
- **Workshop:** not yet; minimum credible path is raw Family 1/2 reproduction plus a
  prompt/context ablation, with Family 4 strongly desirable if RQ5 remains.
- **Full conference:** not ready; requires broader tasks/models, stronger baselines,
  defensible uncertainty analysis, literature-supported novelty, and full evidence.

## Priority plan

1. Start writing the conservative draft now.
2. Reproduce Families 1 and 2 with complete evidence retention.
3. Run prompt/context and workspace-exploration ablations.
4. Execute Family 4 exactly as frozen.
5. Add the closest skill/memory baseline or a model-size comparison after literature
   review.

## Patent/IP note — not legal advice

Publication does not create patent rights. Broad agent memory, experience reuse,
skill generation, and routing have substantial prior art, and the present evidence
does not demonstrate patentability. Seek dedicated IP review before public disclosure
of any potentially novel implementation mechanism if protection is desired.
