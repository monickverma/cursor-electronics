# Circuit OS

**Describe a circuit in plain English → get a validated schematic, Arduino firmware, a SPICE simulation, a bill of materials, and an explanation of every design choice.**

Circuit OS is an AI hardware compiler. It runs on Claude or on **open models served by vLLM on AMD ROCm GPUs** — see [docs/AMD.md](docs/AMD.md).

## The one rule

> The LLM never writes SPICE, KiCad files or firmware directly.

LLMs invent pin numbers and function names. So the model only outputs structured JSON against a strict intermediate representation (IR) schema, and deterministic compilers do everything else:

```
prompt ─► intent parser ─► circuit reasoner ─► IR (JSON)
                                  ▲               │
                                  │   Pydantic + hardware rule engine
                                  └── exact field errors, ≤3 retries
                                                  │
                     ┌──────────────┬─────────────┼──────────────┬───────────┐
                  ngspice        KiCad        Arduino .ino       BOM     explanation
                 simulation    schematic     (Jinja2, compiles)
                 (pass/fail, 15% tolerance)
```

Same input, same output. A wrong part — say 1nF instead of 100nF in an RC filter — fails simulation before anything is built.

## Features

- **Hardware rule engine** — floating nodes, voltage ratings, missing I²C pull-ups, RS-485 termination, PWM-capable pins
- **Simulation** — ngspice runs in the background (Celery + Redis), graded pass/fail
- **Patching** — "make the LED brighter" becomes a small patch that changes only what was asked
- **Explanations that focus on consequences** — not "R3 limits current", but what breaks if you change R3
- **Runs on AMD** — the same pipeline runs on an open model served by vLLM on ROCm, with a benchmark script
- JWT auth, rate limiting, PostgreSQL storage, 400+ passing tests
- Experimental PCB layout engine with an A* router

**v0.1.0 templates:** DHT22 sensor alert · MAX485 Modbus RTU · LED with current-limiting resistor · RC low-pass filter · voltage divider

## Stack

FastAPI · Pydantic v2 · Anthropic SDK / vLLM (OpenAI-compatible) · ngspice · Celery + Redis · PostgreSQL · Next.js · Jinja2

## Quick start

See [SETUP.md](SETUP.md). Short version:

```bash
cp .env.example .env        # set ANTHROPIC_API_KEY, or AI_PROVIDER=openai_compat for vLLM
docker-compose up -d        # PostgreSQL + Redis
pip install -r backend/requirements.txt
python -m pytest -q
start.bat                   # backend + frontend on Windows
```

### On AMD GPUs

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000 --enable-auto-tool-choice --tool-call-parser hermes
AI_PROVIDER=openai_compat AI_MODEL=Qwen/Qwen2.5-7B-Instruct python scripts/amd_benchmark.py
```

Full guide: [docs/AMD.md](docs/AMD.md).

## Roadmap

Free-form circuits beyond the five templates. See [ROADMAP.md](ROADMAP.md).

## License

Copyright (C) 2026 Monick Verma.

Circuit OS is free and open-source software under the **GNU Affero General Public License v3.0** — see [LICENSE](LICENSE). If you modify it, or run a modified version as a network service, you must release your source under the same license. For commercial licensing under different terms, contact the author.
