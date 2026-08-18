# agent-experience-lab

`agent-experience-lab` is a minimal, model-provider-neutral benchmark harness for
coding agents. Its eventual hypothesis is that a successful execution trace from
one coding agent can help a later, cheaper agent solve the same or a similar task
with fewer reasoning steps, tool calls, tokens, failures, and cost.

This project is deliberately **not** an Agent Work Protocol (AWP), A2A, MCP, or
experience-retrieval implementation. It contains no search, embeddings, database,
reputation, signatures, network service, or UI. Milestone 3 accepts one explicitly
selected prior experience; it does not discover, rank, or automatically apply it.

The eventual benchmark will compare four conditions:

| Condition | Model | Prior experience |
| --- | --- | --- |
| A | Frontier | No |
| B | Frontier | Yes |
| C | Small/local | No |
| D | Small/local | Yes |

The harness has one generic agent loop. Model behavior is supplied through a small
`ModelAdapter` interface, so conditions A-D will be configurations rather than
separate agent implementations. The current version includes a deterministic
`MockModelAdapter`, OpenAI and Vertex AI Gemini adapters, direct experience
injection, one exact coding task, and evidence-based successful-run capture.

## Quick start

Python 3.11 or newer is required.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m harness.runner --task task01_exact --model mock
```

## Real-model runs

The OpenAI adapter reads its credential from `OPENAI_API_KEY`; keys are never
hardcoded. In bash or zsh:

```bash
export OPENAI_API_KEY='your-api-key'
```

Run without prior experience:

```bash
python -m harness.runner --task task01_exact --model gpt-5.6-luna
```

Run with one explicitly selected experience:

```bash
python -m harness.runner \
  --task task01_exact \
  --model gpt-5.6-luna \
  --experience experiences/exp_7117ce212ed74cb18208a61707855a89.json
```

Run the two-condition smoke-test comparison:

```bash
python -m harness.runner \
  --task task01_exact \
  --model gpt-5.6-luna \
  --compare-experience experiences/exp_7117ce212ed74cb18208a61707855a89.json
```

The comparison always resets the workspace from the pristine task before each
condition. It does not make a statistical improvement claim from two runs. Both
conditions use the same independently applied step budget; override the default
of 20 with `--max-steps 12`.

Token usage comes from provider response metadata. Cost remains JSON `null` and is
shown as `unsupported` unless both prices are explicitly configured:

```bash
python -m harness.runner \
  --task task01_exact \
  --model gpt-5.6-luna \
  --compare-experience experiences/exp_7117ce212ed74cb18208a61707855a89.json \
  --input-cost-per-million <CURRENT_INPUT_USD> \
  --output-cost-per-million <CURRENT_OUTPUT_USD>
```

## Vertex AI Gemini

The Vertex adapter uses the current `google-genai` SDK with Application Default
Credentials. It requires `GOOGLE_CLOUD_PROJECT`; `GOOGLE_CLOUD_LOCATION` defaults
to Vertex's `global` location when omitted.

Authenticate and configure a local shell:

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT='your-google-cloud-project-id'
export GOOGLE_CLOUD_LOCATION='global'
```

Run Gemini without prior experience:

```bash
python3 -m harness.runner \
  --task task01_exact \
  --provider vertex \
  --model gemini-2.5-flash
```

Run Gemini with one prior experience:

```bash
python3 -m harness.runner \
  --task task01_exact \
  --provider vertex \
  --model gemini-2.5-flash \
  --experience experiences/exp_7117ce212ed74cb18208a61707855a89.json
```

Run the Gemini smoke-test comparison:

```bash
python3 -m harness.runner \
  --task task01_exact \
  --provider vertex \
  --model gemini-2.5-flash \
  --compare-experience experiences/exp_7117ce212ed74cb18208a61707855a89.json
```

The adapter requests structured JSON from Gemini using the same action schema and
prompt renderer as OpenAI. Provider usage metadata populates token counts; cost is
`null` unless explicit pricing flags are supplied.

## Local Ollama experiment

The Ollama adapter calls the local HTTP API at `http://localhost:11434` by
default. Override it when needed:

```bash
export OLLAMA_BASE_URL='http://localhost:11434'
export OLLAMA_TIMEOUT_SECONDS=180
```

`OLLAMA_TIMEOUT_SECONDS` accepts a positive numeric value and defaults to 180.
Increase it for models that need longer to load or generate an action.

Enable request metadata and phase timing without printing prompt contents:

```bash
export OLLAMA_DEBUG=1
```

For explicit local prompt inspection, additionally set:

```bash
export OLLAMA_DEBUG_PROMPT=1
```

Run the three-stage non-mutating diagnostic—trivial chat, tiny structured action,
and the actual Task 02 first-turn prompt—with:

```bash
python3 -m harness.runner \
  --provider ollama \
  --model qwen2.5:0.5b \
  --diagnose-ollama
```

The diagnostic never executes the returned action. Expected Ollama runtime
failures such as timeouts are recorded in benchmark results, allowing the second
comparison condition to continue.

Ollama is not installed, started, or given models automatically. Prepare a model
explicitly, for example:

```bash
ollama pull qwen2.5:7b
```

Run Task 02 without prior experience:

```bash
python3 -m harness.runner \
  --task task02_config_path \
  --provider ollama \
  --model qwen2.5:7b
```

Run with a verified Gemini-produced Task 02 experience:

```bash
python3 -m harness.runner \
  --task task02_config_path \
  --provider ollama \
  --model qwen2.5:7b \
  --experience experiences/<gemini-task02-experience>.json
```

Compare the two Ollama conditions:

```bash
python3 -m harness.runner \
  --task task02_config_path \
  --provider ollama \
  --model qwen2.5:7b \
  --compare-experience experiences/<gemini-task02-experience>.json
```

The intended research sequence is to let Gemini solve Task 02 first, then pass its
evidence-derived experience explicitly to Ollama. The harness does not create fake
experiences or download models. Ollama token metrics come from
`prompt_eval_count` and `eval_count`. Its `estimated_cost_usd` is `0.0`, meaning
direct local API/model cost only; electricity and hardware costs are excluded.

## Experience Recipe v0.2

Recipe v0.2 deterministically compiles the verified Task 02 experience into
compact procedural guidance plus reusable `implementation_concepts`. It uses
known Task 02 metadata plus changed-file, patch, and verification evidence; it
does not call a model, copy the unified diff, or embed final corrected source.

Compile a recipe:

```bash
python3 -m harness.runner \
  --compile-recipe experiences/exp_aedf873f3b13471ea3e0145e4a4c7c2d.json
```

Use only the compiled recipe:

```bash
python3 -m harness.runner \
  --task task02_config_path \
  --provider ollama \
  --model llama3.2:1b \
  --max-steps 12 \
  --recipe recipes/<recipe-id>.json
```

Compare no context, raw experience, and compact recipe from independently reset
workspaces:

```bash
python3 -m harness.runner \
  --task task02_config_path \
  --provider ollama \
  --model llama3.2:1b \
  --max-steps 12 \
  --compare-representations \
  --experience experiences/exp_aedf873f3b13471ea3e0145e4a4c7c2d.json \
  --recipe recipes/<recipe-id>.json
```

Recipe instructions are never executed automatically. The model still works only
through the normal validated actions, and the task's deterministic tests remain
the final authority.

## Repeated runs

Use `--repeat` to rerun one unchanged benchmark condition from a pristine
workspace each time. The default remains one run.

```bash
python3 -m harness.runner \
  --task task02_config_path \
  --provider ollama \
  --model qwen2.5:3b \
  --max-steps 8 \
  --recipe recipes/recipe_98832e7c414d8cb42300e4dbc80d7535.json \
  --repeat 5
```

Every raw run remains in `results/`. One additional `repeat_*.json` records the
success rate, execution/token/time averages, elapsed range, failure-type counts,
and individual run IDs. Test pass/fail counts are not averaged.

## Task 03 cross-task transfer

Task 03 tests bundled template-resource loading from changing working directories.
Its public task metadata contains only the broken behavior, not the expected patch
or implementation mechanism. Portable knowledge is compiled deterministically
from Recipe v0.2:

```bash
python3 -m harness.runner \
  --compile-transfer-knowledge \
  recipes/recipe_98832e7c414d8cb42300e4dbc80d7535.json
```

The resulting `transfer_knowledge/*.json` excludes source-task files, paths,
steps, verification counts, and patches. Apply it as contextual guidance with:

```bash
python3 -m harness.runner \
  --task task03_resource_path \
  --provider ollama \
  --model qwen2.5:3b \
  --max-steps 8 \
  --transfer-knowledge transfer_knowledge/<transfer-id>.json \
  --repeat 5
```

## Kaggle GPU setup

The Transformers provider is optional, so the lightweight harness does not
install PyTorch or Hugging Face packages by default. In a Kaggle notebook with a
GPU enabled under notebook settings, install both requirement sets:

```bash
pip install -r requirements.txt
pip install -r requirements-transformers.txt
```

Run Task 03 with Qwen2.5-7B-Instruct:

```bash
python3 -m harness.runner \
  --task task03_resource_path \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8
```

Run with cross-task transfer knowledge:

```bash
python3 -m harness.runner \
  --task task03_resource_path \
  --provider transformers \
  --model Qwen/Qwen2.5-7B-Instruct \
  --max-steps 8 \
  --transfer-knowledge \
  transfer_knowledge/transfer_a4142b399f8684e6a75fda4a625ed4d8.json
```

The adapter loads and reuses one tokenizer/model instance, uses CUDA
automatically through `device_map="auto"`, and defaults to deterministic greedy
generation. `TRANSFORMERS_MAX_NEW_TOKENS` defaults to `512`, and
`TRANSFORMERS_TEMPERATURE` defaults to `0`. Token counts come directly from the
tokenizer. `estimated_cost_usd` is `0.0`, meaning no direct inference API charge;
Kaggle or other hosted runtime costs are excluded.

Each CLI run:

1. replaces `.workspaces/<task-id>` with a clean copy of the task's source
   workspace;
2. lets the configured adapter use validated structured actions;
3. runs the task's real test command as the final authority;
4. derives changed files and a unified diff by comparing the pristine and active
   workspaces after a successful verification;
5. derives and prints a concise trajectory from executed actions and tool outputs;
6. writes `results/<run-id>.json` and, on success only,
   `experiences/<experience-id>.json`.

Result JSON includes the configured `max_steps`, the concise `trajectory`, and
counts in `trajectory_diagnostics`. File contents and full command output are not
copied into trajectories. A failed run that uses every allowed step without
finishing is recorded as `max_steps_exhausted`; provider failures such as Ollama
timeouts retain their provider-specific failure type.

The agent can only access the copied active workspace. Paths are resolved and
checked before every file operation, symlink/path-traversal escapes are rejected,
and commands are executed without a shell from a small allowlist. The immutable
task source, harness, evaluator configuration, and result validation remain outside
the active workspace.

Before strict tool validation, the provider-neutral agent loop removes fields that
do not belong to the selected action. It never fills missing fields or changes
retained paths and commands, so required-field checks, workspace confinement, and
the command allowlist still run normally.

## Layout

```text
harness/                 generic agent, tools, runner, models, metrics
harness/openai_adapter.py OpenAI Responses API adapter
harness/vertex_adapter.py Vertex AI Gemini adapter
harness/ollama_adapter.py Local Ollama HTTP adapter
harness/transformers_adapter.py Optional local Hugging Face adapter
harness/prompting.py       shared action schema and prompt rendering
harness/repeated.py        repeated-run aggregate metrics
experience/              experience schema and evidence capture
recipe/                  compact deterministic Recipe v0 schema and compiler
transfer/                portable transfer schema and deterministic compiler
tasks/task01_exact/      public task metadata and pristine failing workspace
tasks/task02_config_path/ configuration-path benchmark and pristine workspace
tasks/task03_resource_path/ cross-task bundled-resource benchmark
tests/                   harness and end-to-end tests
results/                 generated benchmark result JSON
experiences/             generated successful experience JSON
.workspaces/             resettable run workspace (generated)
```

`task.json` contains only the public problem statement and deterministic test
command. The expected patch is not included in the model prompt. Success is never
self-reported by the model: the harness always executes the configured tests after
the agent stops. Experience patches come from actual workspace bytes, not model
text or model claims. Failed runs never produce reusable experience records.
When supplied, prior experience is placed in a clearly delimited prompt section as
reference evidence. The model must still inspect and edit the freshly reset
workspace through validated tools, and deterministic tests remain the sole success
criterion.
