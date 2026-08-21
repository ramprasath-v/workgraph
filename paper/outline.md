# Working paper outline

## Recommended title

**When Agent Experience Helps, Fails, and Hurts: Conditional Assistance in
Tool-Using Language-Model Agents**

This title foregrounds the best-supported result—assistance is conditional rather
than monotonically useful—without presenting the narrower “capability displacement”
mechanism as universal. “Experience-conditioned capability displacement” remains a
useful term for the enabling regime, not the umbrella claim.

## Abstract — conservative draft

Tool-using language-model agents can receive prior verified experience, distilled
transfer knowledge, or current-task scouting, but injecting more relevant context
need not improve execution. We present WorkGraph, an experimental harness that
captures successful executions as verification-backed artifacts and measures how
different assistance representations affect a downstream coding agent. Across three
small, hand-built task families using Qwen 2.5 7B as the principal consumer, the
retained evidence contains two contrasting regimes. A new Family 1 reproduction
records baseline failure in 5/5 runs and relevant-transfer success in 5/5, without
test-file writes. A new Family 2 reproduction records the same harness-level rates
but all assisted runs rewrote the test file and finished with only one passing test;
it therefore exposes a verification-integrity threat rather than a clean second
replication. Family 3 retains complete original evidence: on Task 09, unaided Qwen
succeeded in 5/5 runs, whereas relevant historical transfer, irrelevant historical
transfer, a detailed current-task scout, and a compact scout each succeeded in 0/5.
The retained trajectories show representation-dependent regressions, unexpected
writes, verification behavior, and inference costs, but do not establish hidden
reasoning quality. These controlled cases show that external assistance was not
monotonically beneficial in this harness. They do not establish population-level
generalization. We preregistered a deterministic policy that selects no assistance,
historical transfer, compact scouting, or escalation, together with a held-out
Family 4 protocol; that policy has not yet been evaluated.

## 1. Introduction

- Motivate verified execution as a potential inference-time resource rather than
  unconditionally useful memory.
- State the central tension: assistance can supply missing capability, consume
  context, redirect exploration, or induce harmful changes.
- Present the contribution as controlled measurement of conditional assistance,
  not proof that experience generally helps or hurts.
- State the evidence-retention asymmetry up front.

## 2. Research Questions

- **RQ1 — Capability enabling:** Can verified prior agent experience enable a
  target model that fails unaided?
- **RQ2 — Assistance insufficiency:** When does assistance fail to overcome the
  consumer agent’s execution limitations?
- **RQ3 — Interference:** Can correct or relevant assistance interfere with a
  model that already succeeds unaided?
- **RQ4 — Representation and cost:** How do raw/detailed and compact assistance
  representations affect observable execution behavior and inference cost?
- **RQ5 — Selection policy:** Can a leakage-free pre-execution policy choose among
  unaided execution, historical transfer, current-task scouting, and escalation?
  **Not yet evaluated.** Policy v0.1 and Family 4 are preregistered but unrun.

## 3. WorkGraph Concept

Describe the lifecycle:

1. execute a bounded tool-using task;
2. verify success deterministically;
3. capture actual changed files, patch, task/model metadata, and test results;
4. distill a recipe and portable transfer abstraction;
5. optionally acquire a read-only current-task scout and compile it compactly;
6. inject at most one assistance representation into a consumer run;
7. measure verified success, trajectories, tokens, time, and regressions;
8. eventually select assistance before execution using a frozen policy.

The producer’s claim is not sufficient: verified experience is grounded in observed
workspace differences and deterministic evaluation.

## 4. Definitions

- **Verified experience:** A structured record created only after deterministic
  task success, containing task/model metadata, observed workspace changes, an
  actual unified diff, verification command/results, and timestamps.
- **Recipe:** A deterministic, compact same-task distillation of verified
  experience. It omits the raw patch and expresses target, goal, constraints,
  verification, and implementation concepts.
- **Transfer knowledge:** A deterministic portable abstraction compiled from a
  recipe for a different task. It contains generalized principles and implementation
  concepts, not the original patch or target identifiers.
- **Detailed current-task scout:** A provenance-bearing handoff produced by one
  read-only model inspection of the public current task and copied workspace.
- **Compact scout:** A deterministic, model-free reduction of a detailed scout into
  concise principles and implementation concepts with acquisition provenance.
- **Assistance condition:** A run in which exactly one preregistered context artifact
  is supplied, or execution is assigned to a frozen escalation model.
- **Unaided condition:** The target model receives the normal public task context and
  tool history, with no experience, transfer, or scout artifact.
- **Capability displacement:** A narrow observed regime in which assistance is
  associated with success by a consumer that failed unaided. It is not a general
  synonym for any behavior change.
- **Assistance-insufficient regime:** Assistance changes or directs execution but
  does not produce deterministic verified success.
- **Assistance-induced interference / negative transfer:** An assisted condition
  performs worse than the matched unaided condition. “Negative transfer” here is a
  condition-level outcome, not proof of a cognitive mechanism.
- **Target model:** The model whose task performance and resource use are the primary
  downstream outcomes.
- **Escalation model:** A stronger model selected before execution and run directly
  from pristine state; it is not a post-failure rescue.
- **Verification:** The frozen deterministic evaluator result, distinct from an
  agent choosing to call the test tool during its trajectory.
- **Expected cost per verified success:** Total preregistered strategy cost divided
  by verified successes; undefined/null when success count is zero.

## 5. Experimental Method

- Describe the shared tool interface, strict validation, normalized structured
  actions, pristine reset, fixed step budget, and deterministic pytest evaluator.
- Separate producer verification, artifact compilation, and consumer execution.
- Describe five context conditions: none, relevant historical, irrelevant
  historical, detailed scout, compact scout.
- Explain the predeclared Task 09 analysis contract and trajectory definitions.
- Report Qwen generation as deterministic (`temperature=0`, `do_sample=false`), so
  repeated runs must not automatically be treated as independent random samples.
- State retention: complete new Family 1/2 core reproductions and complete original
  Family 3 evidence; original Family 1/2 Kaggle evidence remains unavailable.

## 6. Results

- Use `paper/evidence-table.md` as the authoritative presentation table.
- Present Family 1/2 historical observations separately from their new versioned,
  provenance-labeled reproductions, including Family 2's test-write finding.
- Present Family 3 numerical values from `paper/evidence-summary.json`, which is a
  deterministic projection of the frozen checkpoint/results.
- Do not pool the three hand-built families into a population estimate.

## 7. Behavioral Analysis

- Family 3 baseline: verified success despite persisted malformed/invalid-action
  signals; operational metrics can coexist and require careful interpretation.
- Relevant transfer: 0/5, max-step exhaustion in all runs, four predeclared passing
  tests regressed on average, unexpected writes in all runs.
- Irrelevant transfer: 0/5 but retained four pristine passing tests on average; no
  unexpected writes.
- Detailed scout: 0/5, all six final tests failed on average, no relevant-source
  read recorded, but relevant writes and verification were present.
- Compact scout: 0/5, all six final tests failed on average, verification-use rate
  zero, and max-step exhaustion in all runs.
- These are observable trajectories, not direct measurements of reasoning quality.

## 8. Discussion

Strongest defensible claim:

> Verified external assistance can enable a consumer that fails unaided, while
> assistance injection can also interfere with a consumer that succeeds unaided;
> assistance utility is conditional rather than monotonic.

The enabling contrast is machine-derived from the new Family 1 reproduction. The
interference result is machine-derived from Task 09 with Qwen 2.5 7B, this harness,
and an eight-step budget. Family 2's historical 0/5→0/5 pattern did not reproduce.

Discuss plausible mechanisms as hypotheses only: context competition, anchoring,
premature editing, reduced exploration, tool-schema friction, or consumer-capability
mismatch. Prompt/context ablations are needed to distinguish them.

## 9. Related Work Positioning

The current repository contains no source-backed literature bibliography; citations
must be added in a dedicated review before submission. The positioning is therefore
provisional:

- Skill synthesis and SkillGen/SkillOpt-like approaches motivate generating reusable
  procedural abstractions; skill generation itself is not claimed as novel.
- Experience and memory systems, including ReasoningBank-like approaches, motivate
  retaining and reusing prior traces or lessons; experience reuse itself is not
  claimed as novel.
- Model/task routing motivates conditional allocation; routing itself is not novel.
- Current-task scouting resembles inference-time analysis or planning assistance;
  scouting itself is not claimed as novel.

Potential differentiation under investigation is the treatment of verified work as
an inference-time capability/economic resource, explicit measurement of benefit and
harm conditional on consumer capability, and selective assistance rather than
unconditional memory injection. This is positioning, not established novelty.

## 10. Threats to Validity

Use `paper/reviewer-risks.md`. Emphasize task-construction bias, one principal small
consumer, deterministic repeats, missing original evidence, test-write integrity,
prompt interference,
harness-specific behavior, and weak comparison baselines.

## 11. Limitations

- Three small hand-built families; only Family 3 has complete original evidence,
  while Families 1/2 have separately versioned core reproductions.
- Primarily Qwen 2.5 7B as consumer; no model-size frontier.
- Five largely deterministic repetitions per condition.
- No closest skill/memory, automatic retrieval, or routing baseline.
- No dollar-cost table or statistical uncertainty estimates.
- Public tests may be visible to current-task scouts.
- Family 4 policy remains untested.

## 12. Future Work

Prioritize alternative-explanation ablations, verification hardening, policy validation,
model breadth, and established baselines. Keep automatic retrieval and learned policy
work separate from the first controlled claim.

## 13. Conclusion

Conclude narrowly: WorkGraph exposes assistance as a conditional intervention whose
verified value depends on task, consumer, and representation. The current evidence
justifies further study and a transparent technical report, not a general theorem of
agent memory or an established routing policy.

## Proposed figures and tables

- **Figure 1:** WorkGraph verified-experience lifecycle.
- **Figure 2:** Three observed assistance regimes, with provenance labels.
- **Figure 3:** Family 3 Task 09 success, token, and regression comparison.
- **Table 1:** Artifact definitions.
- **Table 2:** Cross-family evidence and retention status.
- **Table 3:** Family 3 behavioral and cost metrics.
- **Table 4:** Threats and validity controls.

No publication graphics are generated in this checkpoint.

## Patent / IP note — not legal advice

Publishing does not create a patent. Broad agent memory, reuse, skill synthesis, and
routing concepts have substantial prior art, and the present evidence does not itself
demonstrate patentability. If protection is desired for a potentially novel
implementation mechanism, obtain dedicated IP review before public disclosure. This
section makes no legal conclusion.
