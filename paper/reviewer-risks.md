# Reviewer risks, readiness, and experiment priorities

## Reviewer-risk table

| Risk | Severity | Likely objection | Current repository response | Recommended mitigation | Family 4 addresses it? |
|---|---|---|---|---|---|
| A. Three small hand-built families | High | Cases may be idiosyncratic | Tasks and freeze controls are transparent | Add more independently designed held-out tasks/domains | Partially: three new tasks, still hand-built |
| B. Primarily one small consumer | High | Effects may be specific to Qwen 7B | Model/provider provenance is retained | Test at least one smaller and one stronger consumer | No; Task 10 adds Gemini but is not a model frontier |
| C. Five repetitions | High | Rates are unstable | Raw Family 3 runs and denominators are explicit | Add justified uncertainty and more runs where stochasticity is real | No; Family 4 also uses five |
| D. Deterministic Qwen repeats | High | Runs may be duplicates rather than independent samples | Actual `do_sample=false` behavior is documented | Treat repeats as robustness checks; add a preregistered stochastic condition if valid | No |
| E. Missing original Family 1/2 evidence | Medium-high | New reproductions cannot recover the original runs | Versioned core reproductions are retained and explicitly separated from history | Preserve provenance and avoid claiming original replication beyond frozen rules | No |
| E2. Test-mutation verification integrity | High | A model can obtain harness success by weakening public tests | Family 2 manifest records five test-file writes and only one final passing test | Prevent test writes or evaluate against a separate pristine copy in a future frozen harness revision | No |
| F. Task-construction bias | High | Tasks may encode expected assistance regimes | Frozen tasks/artifacts and predeclared analysis contracts help | Independent task authoring, blinded design, and more held-out cases | Partially: policy precedes Family 4 tasks |
| G. Prompt/context interference alternative | High | Failures may reflect length/format, not knowledge content | Token accounting and irrelevant controls exist | Length-matched, placement, paraphrase, and empty-context ablations | No |
| H. No closest skill/memory baseline | High | WorkGraph is not compared with established memory methods | Artifact representations are explicit | Implement the closest reproducible skill/memory baseline | No |
| I. No automatic retrieval experiment | Medium | Manual artifact assignment avoids retrieval errors | Policy inputs and lexical selection are transparent | Add retrieval only after fixed-injection effects are understood | No |
| J. No model-size frontier | High | “Capability” interpretation lacks capacity variation | Model identity is frozen per run | Sweep at least two consumer sizes under identical tasks | No |
| K. No statistical uncertainty | Medium | Point estimates overstate precision | No significance claims are made | Report intervals appropriate to the sampling design; avoid pseudo-independence | No |
| L. No dollar-cost comparison | Medium | Token/time differences lack economic interpretation | Token and elapsed accounting is retained | Freeze provider prices and calculate strategy dollars/success | Family 4 protocol supports it, but execution is absent |
| M. Scouts may see public tests | Medium | Scout advantage is not comparable to historical transfer | Scout permissions are explicit | Add scout-without-tests ablation or justify public-test access | No |
| N. Harness-specific prompting artifact | High | Family 3 may arise from prompt/schema interactions | Same harness and action schema are held constant | Prompt placement/length ablations and an alternate agent harness | No |
| O. Policy v0.1 untested | High for policy claims | Routing hypothesis has no outcome evidence | Policy/tasks/manifest are prospectively frozen | Execute Family 4 exactly as preregistered | **Yes, directly** |

## Should Family 4 be run before submission?

**Recommendation: conditional go, but not as the first missing validation.** Family 4
is the highest-value test of RQ5 and uniquely benefits from prospective freezing. It
does not isolate the Family 3 mechanism or repair Family 2 verification integrity,
does not add a closest baseline, and does not distinguish knowledge effects from
prompt/context interference. For a first credible workshop draft, start writing now,
restore Families 1/2 evidence first, then run Family 4 without changing its manifest.

## Ranked experiment portfolio

Ratings are qualitative planning judgments, not experimental results. Effort and
compute use low/medium/high, where lower is cheaper.

| Rank | Candidate | Scientific value | Reviewer value | Engineering effort | Compute cost | Effect on credibility |
|---:|---|---|---|---|---|---|
| 1 | Minimum Task 09 wrapper/context/authority ablation | High | High | Medium | Medium | Tests the strongest alternative explanation for Family 3 |
| 2 | Harden pristine-test verification prospectively | High | High | Medium | Low | Prevents Family 2-style false-positive harness success |
| 3 | Run preregistered Family 4 | High for RQ5 | High | Medium | High | Prospectively evaluates selection policy; does not repair RQ1/RQ2 evidence |
| 4 | Closest skill/memory baseline | High | High | High | Medium | Establishes comparative relevance to prior systems |
| 5 | Additional consumer-model sizes | High | High | Medium | High | Tests the consumer-capability interpretation |
| 6 | Monetary cost per verified success | Medium | Medium-high | Low | Low | Converts existing accounting into practical comparison |
| 7 | Stochastic repetitions where valid | Medium | Medium | Low-medium | High | Improves robustness only if the sampling process is meaningful |
| 8 | Model-routing baseline | Medium | Medium | Medium | High | Separates WorkGraph selection from ordinary escalation/routing |
| 9 | Assistance-suppresses-exploration analysis | Medium | Medium | Medium | Low | Useful mechanism evidence, but needs preregistered measures/ablations |
| 10 | Automatic retrieval | Medium later | Medium | High | Medium | Adds a new failure source before fixed-assistance effects are settled |

## Publication readiness

| Venue level | Ready now? | Biggest blockers | Minimum additional work |
|---|---|---|---|
| Internal research note | **Yes** | Evidence asymmetry must stay visible | Preserve provenance labels and frozen hashes |
| Public technical report / preprint | **Conditional** | Mechanism unresolved; Family 2 integrity issue; no literature baseline | Run minimum ablation, narrow claims, complete citations, publish data/method limits |
| Workshop paper | **No, closer after reproduction** | Weak breadth, mechanism unresolved, no closest baseline, policy untested | Run key ablation; harden verification prospectively; preferably run Family 4 or narrow out RQ5 |
| Full conference paper | **No** | Model/task breadth, statistical design, baselines, novelty evidence | Multi-model/task expansion, established baselines, uncertainty analysis, full related work, replicated raw evidence |

## Paper-readiness scorecard

| Dimension | Rating | Reason |
|---|---|---|
| Research-question clarity | Strong | Five questions separate enabling, insufficiency, interference, representation, and policy |
| Methodological discipline | Strong | Freeze points, deterministic evaluation, leakage tests, and preregistration are unusually explicit |
| Reproducibility | Moderate-to-strong | Family 3 and new Family 1/2 core reproductions retain raw runs; original Family 1/2 evidence remains absent |
| Evidence breadth | Weak | Three small hand-built families and one principal consumer remain insufficient for broad claims |
| Statistical strength | Weak | n=5 and deterministic generation do not support population inference |
| Model breadth | Weak | Primarily one Qwen 7B consumer |
| Comparison-baseline strength | Weak | No closest skill/memory or routing baseline |
| Novelty confidence | Weak-to-moderate | Positioning is plausible, but source-backed literature review is absent |
| Practical significance | Moderate | Token/time and regression effects are concrete, but dollar cost is missing |
| Narrative coherence | Moderate-to-strong | The three conditional regimes form a clear story if provenance asymmetry remains explicit |

## Ranked immediate plan

1. **Start writing now** from the frozen skeleton, retaining provenance labels.
2. **Run the minimum prompt/context/authority ablation** on Family 3.
3. **Harden pristine-test verification prospectively** without reinterpreting frozen runs.
4. **Execute Family 4 exactly as preregistered** after the two higher-priority
   evidence checks; do not redesign it based on the draft.
5. **Add one closest skill/memory baseline or model-size comparison**, chosen after
   the literature review clarifies the strongest reviewer expectation.
