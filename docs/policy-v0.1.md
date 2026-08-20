# WorkGraph assistance-selection Policy v0.1

## Freeze point and hypothesis

Policy v0.1 is predeclared after the frozen Families 1–3 checkpoint and before any
Family 4 task is created or observed. It is deterministic, auditable, and makes its
choice before target-model execution.

The hypothesis to test—not an established result—is:

> A leakage-free assistance-selection policy can outperform unconditional
> assistance by preserving unaided success when the model is already sufficient
> while still using assistance or escalation when unaided capability is uncertain
> or insufficient.

The policy chooses exactly one action:

- `NO_ASSISTANCE`
- `HISTORICAL_TRANSFER`
- `COMPACT_CURRENT_TASK_SCOUT`
- `ESCALATE`

## Machine-readable output schema

```json
{
  "policy_version": "0.1",
  "decision": "NO_ASSISTANCE | HISTORICAL_TRANSFER | COMPACT_CURRENT_TASK_SCOUT | ESCALATE",
  "signals": {
    "target_model_capability_tier": "low | standard | high",
    "target_language_supported": true,
    "source_file_count": 2,
    "source_type_count": 1,
    "workspace_uncertainty": "low | medium | high",
    "historical_transfer_available": true,
    "historical_transfer_verified": true,
    "transfer_public_overlap": 0.5,
    "transfer_context_ratio": 0.05,
    "transfer_qualified": true,
    "compact_scout_available": false,
    "compact_scout_already_acquired": false,
    "compact_scout_permitted": false,
    "compact_scout_context_ratio": 0.0,
    "compact_scout_qualified": false
  },
  "rationale_codes": [
    "VERIFIED_TRANSFER_HIGH_PUBLIC_OVERLAP"
  ]
}
```

The exact thresholds and ordered rule descriptions are frozen in
`policy/policy_v0_1.json`.

## Legal pre-execution inputs

Policy v0.1 accepts only:

- public task description and declared language;
- a deterministic list of workspace-relative source paths;
- target model identity, an independently predeclared capability tier, supported
  languages, and context-window size;
- availability and verification status of a historical portable transfer;
- the transfer's portable principles/concepts and estimated context tokens;
- availability, prior acquisition, schema validity, explicit condition permission,
  and estimated context tokens for a compact current-task scout.

The workspace profiler reads paths and suffixes only. It excludes conventional test
paths and never reads source or test contents. Transfer similarity is an overlap
coefficient over normalized tokens in the public task description and portable
abstraction. It uses no embeddings, retrieval service, synonyms, or learned model.

Workspace uncertainty is structural:

- `high`: at least nine source files or at least three source suffix types;
- `medium`: at least four source files or exactly two source suffix types;
- `low`: otherwise.

This is not a researcher-supplied difficulty label.

## Forbidden inputs

The typed schema rejects unknown fields. Policy v0.1 cannot accept:

- hidden evaluator results or target test outcomes;
- producer patches, expected solutions, or corrected source;
- any historical result on the current target task;
- current or future target-model trajectories;
- post-run outcomes;
- manually supplied labels stating whether assistance is needed; or
- task-family identifiers used as routing shortcuts.

## Exact ordered decision rules

The first matching rule wins:

1. `ESCALATE` / `TARGET_LANGUAGE_UNSUPPORTED` when the public task language is
   absent from the target model's supported-language profile.
2. `NO_ASSISTANCE` / `HIGH_CAPABILITY_PRESERVE_UNAIDED` when a language-compatible
   target model has the independently predeclared `high` capability tier.
3. `HISTORICAL_TRANSFER` / `VERIFIED_TRANSFER_HIGH_PUBLIC_OVERLAP` when a portable
   transfer is available and verified, public-text overlap is at least `0.35`, and
   estimated transfer tokens use at most `15%` of the target context window.
4. `COMPACT_CURRENT_TASK_SCOUT` / `COMPACT_SCOUT_ALREADY_ACQUIRED` when a compact
   scout is available, already acquired, explicitly permitted for the condition,
   schema-valid, and uses at most `15%` of the target context window.
5. `ESCALATE` / `LOW_CAPABILITY_WITHOUT_QUALIFIED_ASSISTANCE` for a `low`-tier model
   when neither assistance rule qualified.
6. `ESCALATE` / `HIGH_STRUCTURAL_UNCERTAINTY` when workspace uncertainty is `high`
   and neither assistance rule qualified.
7. `NO_ASSISTANCE` / `DEFAULT_PRESERVE_UNAIDED` otherwise.

These rules contain no path, retry, state-consistency, family, or task-specific
branch. High-tier unaided execution deliberately precedes assistance to protect
potential unaided success. Qualified transfer precedes an already-acquired scout
because it requires no current-task scout acquisition and has direct public-text
support. Family 4 must count any scout acquisition cost even if the policy selects
another action after observing only its allowed metadata.

## Proposed held-out Family 4 experiment — design only

Family 4 should contain three fresh consumer cases selected under three
pre-registered, public-metadata strata:

1. a language-compatible high-tier target model and a compact, single-language
   workspace;
2. a language-compatible standard-tier target model, a modest workspace, and at
   least one independently verified portable transfer candidate; and
3. a language-compatible non-high-tier target model with a structurally broader
   workspace and a compact scout acquired under the uniform scout protocol.

These are sampling strata, not desired policy outcomes: transfer overlap, context
budget, and the actual deterministic workspace profile are computed only after each
fresh case is frozen, and the policy may select any legal action. Researchers may
design structural and capability diversity, but the policy input must not contain
`easy`, `medium`, `hard`, expected success, or an assistance-needed label. Tasks are
created only after this policy is committed.

Each fresh task should have:

- a frozen public description and workspace;
- an analysis contract declared before any model sees it;
- one eligible verified historical portable transfer from a distinct producer;
- one independently generated compact current-task scout;
- deterministic verification; and
- no reuse of Families 1–3 identifiers or solutions.

Run the same target model and fixed step budget under five arms:

A. Policy v0.1
B. Always no assistance
C. Always historical transfer
D. Always compact current-task scout
E. Always escalate

The escalation model and model capability tiers must be declared before task
outcomes. In the policy arm, if compact-scout availability is permitted, acquire it
under a uniform predeclared protocol and include that acquisition in total cost even
when another action is selected. The decision record must be saved before launching
the target or escalated model.

Primary outcomes:

- deterministic verified success;
- total inference tokens and elapsed time, including scout acquisition;
- escalation rate;
- unexpected-write and passing-test-regression metrics where predeclared contracts
  make them measurable; and
- cost per verified success, with zero-success denominators reported as undefined
  rather than coerced.

Report task-level outcomes before pooling across the approximately three cases.
Compare the frozen policy with every fixed arm. A retrospective best-action oracle
may be reported only as a labeled upper bound and never as a policy feature.

No Family 4 task, router integration, embedding, retrieval system, learned
classifier, model call, or benchmark is implemented by this specification.
