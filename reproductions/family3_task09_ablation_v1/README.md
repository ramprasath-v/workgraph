# Task 09 assistance-interference ablation v1

This directory freezes three new conditions. The retained baseline and authoritative
relevant-transfer conditions are anchors and must not be rerun. Run the commands in
the listed order on Lightning AI, preserving five run JSON files and one aggregate
JSON after each command. A nonzero exit is a benchmark outcome, not a reason to
change the next condition.

The shared `optional-context-v1` wrapper, prompt position, task, model, step budget,
and generation settings remain constant. Each control explicitly protects
`test_role_index.py`; a hash change makes the run unsuccessful even if pytest exits
zero.

## 1. EMPTY_ASSISTANCE_WRAPPER

```bash
export TRANSFORMERS_TEMPERATURE=0
export TRANSFORMERS_MAX_NEW_TOKENS=512

python3 -m harness.runner \
  --task task09_role_changes \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --repeat 5 \
  --assistance-control reproductions/family3_task09_ablation_v1/empty_assistance_wrapper.json
```

## 2. NEUTRAL_LENGTH_MATCHED_CONTEXT

```bash
python3 -m harness.runner \
  --task task09_role_changes \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --repeat 5 \
  --assistance-control reproductions/family3_task09_ablation_v1/neutral_length_matched_context.json
```

## 3. RELEVANT_PRINCIPLE_NO_AUTHORITY

```bash
python3 -m harness.runner \
  --task task09_role_changes \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --repeat 5 \
  --assistance-control reproductions/family3_task09_ablation_v1/relevant_principle_no_authority.json
```

Do not create `evidence_manifest.json` until all three retained condition outputs
have been returned and validated. Do not run Family 4.
