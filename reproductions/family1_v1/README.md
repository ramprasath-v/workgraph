# Family 1 Task 04 retained-evidence reproduction v1

This directory preregisters a **new reproduction**, not a reconstruction of the
lost original Kaggle runs. The historical project record reports baseline 0/5 and
relevant transfer 5/5, but those raw files remain unavailable.

The local environment has no CUDA or MPS device and its Torch installation emits a
NumPy binary-compatibility warning. No local Qwen execution was attempted. Execute
the two conditions manually on Kaggle only after committing the preregistration.

## Frozen commands

Run baseline first:

```bash
TRANSFORMERS_TEMPERATURE=0 TRANSFORMERS_MAX_NEW_TOKENS=512 \
python3 -m harness.runner \
  --task task04_report_resources \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --repeat 5
```

Then run the relevant transfer without adapting anything:

```bash
TRANSFORMERS_TEMPERATURE=0 TRANSFORMERS_MAX_NEW_TOKENS=512 \
python3 -m harness.runner \
  --task task04_report_resources \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --repeat 5 \
  --transfer-knowledge transfer_knowledge/transfer_a4142b399f8684e6a75fda4a625ed4d8.json
```

A fully unsuccessful aggregate makes the CLI return status 1; that is an expected
benchmark outcome, not permission to alter the second condition.

## Evidence return procedure

For each printed `aggregate=results/<ID>.json` path, return that aggregate and the
five exact run files listed in its `individual_runs`. Do not rename or rewrite them.
Also return normally generated experience files referenced by successful run JSON,
if any, without compiling them. After both conditions are present, the offline stage
will validate identities and hashes, write `evidence_manifest.json`, run the frozen
trajectory analyzer, and classify the reproduction.
