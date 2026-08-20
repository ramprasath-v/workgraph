# WorkGraph Family 4 preregistration

Family 4 was created after Policy v0.1 was committed. No target model outcome was
observed while designing or freezing these cases. The strata are sampling metadata,
not researcher-supplied difficulty labels or desired policy outcomes.

## Frozen held-out cases

- Stratum A — `task10_booking_boundaries`: back-to-back calendar intervals are
  incorrectly rejected at a shared boundary. The workspace has one Python source
  file and the predeclared target profile is `gemini-2.5-flash`, tier `high`.
- Stratum B — `task11_notification_retries`: repeated notification submissions do
  not preserve the first delivery outcome and conflicting key reuse is accepted.
  The workspace has three Python source files and the predeclared target profile is
  `Qwen/Qwen2.5-7B-Instruct`, tier `standard`. Its independently eligible frozen
  transfer candidate is `transfer_93a42588ddd62085a6289d9b12613079`.
- Stratum C — `task12_discounted_tax`: discounted invoices use the wrong taxable
  amount. The workspace has nine Python source files and the predeclared target
  profile is `Qwen/Qwen2.5-7B-Instruct`, tier `standard`. A compact scout is
  permitted in a later condition but does not yet exist.

Each pristine evaluator reports four passing and two failing tests. Analysis
contracts are stored in task metadata for post-run measurement, but the harness
passes only `task_id`, public description, tools, and history to the model.

## Frozen policy outcomes

The authoritative legal inputs and complete signals are in
`preregistrations/family4_policy_v0_1.json`.

| Task | Policy v0.1 decision | Rationale |
|---|---|---|
| `task10_booking_boundaries` | `NO_ASSISTANCE` | `HIGH_CAPABILITY_PRESERVE_UNAIDED` |
| `task11_notification_retries` | `NO_ASSISTANCE` | `DEFAULT_PRESERVE_UNAIDED` |
| `task12_discounted_tax` | `ESCALATE` | `HIGH_STRUCTURAL_UNCERTAINTY` |

The Stratum B transfer has deterministic lexical overlap `0.086957` and context
ratio `0.001984`. It therefore remains unqualified under the frozen `0.35`
threshold. The task and description were not changed after observing this result.
Stratum C is evaluated truthfully with no acquired scout.

## Future five-condition matrix

Nothing in this matrix is executed by this milestone.

| Condition | Task 10 | Task 11 | Task 12 |
|---|---|---|---|
| Policy v0.1 | Run unaided | Run unaided | Run frozen escalation protocol |
| Always no assistance | Run unaided | Run unaided | Run unaided |
| Always historical transfer | Requires frozen assignment | Use existing retry transfer | Requires frozen assignment |
| Always compact current-task scout | Requires compact scout | Requires compact scout | Requires compact scout |
| Always escalate | Requires frozen escalation protocol | Requires frozen escalation protocol | Requires frozen escalation protocol |

Artifacts and specifications still required after preregistration:

- read-only detailed scouts and deterministic compact-scout artifacts for all three
  tasks, acquired under one uniform protocol;
- fixed historical-transfer assignments for Tasks 10 and 12 (no transfer may be
  created or tuned from a Family 4 outcome);
- a frozen escalation model/provider profile and acquisition-cost schedule; and
- a benchmark execution manifest fixing repetitions, step budgets, artifact hashes,
  and accounting before any target run.

Primary outcomes are verified success, total inference tokens, elapsed time,
escalation rate, unexpected-file-write rate, passing-test regression count, and cost
per verified success. Applicable scout and escalation acquisition costs are included.
