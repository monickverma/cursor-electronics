# Running Circuit OS on AMD GPUs

Circuit OS can run its whole AI layer — intent parsing, IR generation with the
validate-and-retry loop, patching and explanations — on an **open model served
by vLLM on AMD ROCm**, instead of a hosted API. Nothing else in the pipeline
changes: the model still only emits JSON against the IR schema, and Pydantic,
the hardware rule engine and ngspice still decide whether that JSON is a real
circuit.

## Why this fits Circuit OS

Open models are more likely than frontier models to invent a pin, leave a node
floating or forget a pull-up. Circuit OS was built assuming the model *will*
get things wrong:

- **Constrained output.** A forced `tool_choice` becomes a named function call,
  which vLLM enforces with guided decoding, so the output always parses as JSON
  matching the tool schema.
- **Validation with exact feedback.** Schema and rule-engine errors are sent back
  field by field, up to three attempts.
- **Deterministic compilers.** SPICE, KiCad, firmware and BOM never come from the model.

That makes a 7B model running on one AMD GPU usable here, and the benchmark
script measures how much the retry loop is doing.

## 1. Start a GPU session

1. Open <https://notebooks.amd.com/hackathon> and sign in with your AMD Developer Program account.
2. Click **Launch Notebook** and open JupyterLab.
3. Clone into persistent storage — `/persistent` if your URL contains
   `jupyter-hack-`, otherwise `/workspace`:

```bash
cd /persistent   # or /workspace
git clone https://github.com/monickverma/cursor-electronics.git
cd cursor-electronics
pip install -r backend/requirements.txt
```

Check the GPU: `rocm-smi` (or `amd-smi list`).

## 2. Serve an open model with vLLM on ROCm

In a JupyterLab terminal:

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --max-model-len 16384 \
  --enable-auto-tool-choice --tool-call-parser hermes
```

If `vllm` is not installed on the image, use AMD's ROCm build of vLLM
(`rocm/vllm` container or the ROCm wheel from the vLLM docs). Larger models
(e.g. `Qwen/Qwen2.5-32B-Instruct`) fit on AMD Instinct GPUs with more memory.

Wait for `Application startup complete`, then check:

```bash
curl -s localhost:8000/v1/models
```

## 3. Point Circuit OS at it

```bash
export AI_PROVIDER=openai_compat
export OPENAI_BASE_URL=http://localhost:8000/v1
export AI_MODEL=Qwen/Qwen2.5-7B-Instruct
export AI_TIMEOUT_SECONDS=120
```

The same variables go in `.env` to run the full app (`start.bat` / docker-compose).

## 4. Benchmark

```bash
python scripts/amd_benchmark.py --out docs/benchmarks/qwen2.5-7b-rocm.md
```

For every prompt it records whether a valid IR was produced, how many model
calls it took (intent parse + generation + retries) and latency. Run the same
script with `AI_PROVIDER=anthropic` to compare against Claude, and commit both reports.

Stop the session with **Turn-off Session** when you're done; idle time counts
against the 3-hour daily quota.

## How it works

`backend/ai/openai_compat.py` exposes an OpenAI-compatible `/v1/chat/completions`
server through the parts of the Anthropic SDK the AI layer uses
(`messages.create`, `content[0].input/.text`, `stop_reason`), and turns HTTP
failures into the `anthropic` exception types the routes already map to 503/504.
`backend/ai/client.py` picks the backend from `AI_PROVIDER`.
Tests: `tests/test_openai_compat.py`.
