# Family 2 retained-evidence reproduction v1

This directory preregisters a new reproduction. It does not reconstruct the
unretained original Task 07 runs. Execute the two conditions in order on the
Lightning AI Tesla T4, preserving each condition's five run JSON files and
aggregate JSON before starting the next condition.

## F2R_BASELINE

```bash
export TRANSFORMERS_TEMPERATURE=0
export TRANSFORMERS_MAX_NEW_TOKENS=512

python3 -m harness.runner \
  --task task07_retry_transfer \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --repeat 5
```

Preserve the five run JSON files and aggregate JSON exactly as created. A
nonzero process exit is expected when one or more repetitions fail; this does
not invalidate the retained benchmark evidence.

## F2R_RELEVANT_TRANSFER

Run only after preserving baseline evidence, with no intervening adaptation.

```bash
export TRANSFORMERS_TEMPERATURE=0
export TRANSFORMERS_MAX_NEW_TOKENS=512

python3 -m harness.runner \
  --task task07_retry_transfer \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --transfer-knowledge transfer_knowledge/transfer_93a42588ddd62085a6289d9b12613079.json \
  --repeat 5
```

After both conditions, create `evidence_manifest.json` from the returned files.
Do not rename or rewrite result JSON. Retain and hash normally generated
successful-experience artifacts without compiling or injecting them.
