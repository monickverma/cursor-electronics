"""Benchmark Circuit OS's AI layer against any provider — built for vLLM on AMD GPUs.

Runs a fixed set of prompts through the real pipeline (IntentParser →
CircuitReasoner with its validate-and-retry loop) and reports, per prompt:
whether a valid IR came out, how many model calls it took, and wall-clock
latency. Needs no database, Redis or frontend.

Usage (on an AMD Developer Cloud notebook, after `vllm serve ...`):

    AI_PROVIDER=openai_compat AI_MODEL=Qwen/Qwen2.5-7B-Instruct \\
        python scripts/amd_benchmark.py --out docs/benchmarks/qwen2.5-7b-rocm.md

Same script against Claude, for comparison:

    AI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... python scripts/amd_benchmark.py
"""

import argparse
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

# Settings validates at import; the benchmark never touches these.
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "benchmark-only-secret-key-32-characters")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from ai.circuit_reasoner import CircuitGenerationError, CircuitReasoner  # noqa: E402
from ai.intent_parser import IntentParser  # noqa: E402
from core.config import settings  # noqa: E402

PROMPTS = [
    "Blink an LED on an Arduino Uno with a current-limiting resistor",
    "DHT22 temperature and humidity sensor on an Arduino Uno that alerts above 30C",
    "RC low-pass filter with a 1kHz cutoff",
    "Voltage divider that turns 12V into 5V for an ADC input",
    "Arduino Uno as a Modbus RTU master over RS-485 using a MAX485",
]


class _CountingClient:
    """Wraps a client so each model call is counted — retries show up here."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        return self._inner.messages.create(**kwargs)


def _gpu_name() -> str:
    for cmd in (["rocm-smi", "--showproductname"], ["amd-smi", "list"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                if any(k in line for k in ("Card series", "Card SKU", "GPU", "Instinct", "Radeon")):
                    return line.split(":", 1)[-1].strip() or line.strip()
        except (OSError, subprocess.SubprocessError):
            continue
    return "unknown (rocm-smi not found)"


def run() -> list[dict]:
    results = []
    for prompt in PROMPTS:
        parser, reasoner = IntentParser(), CircuitReasoner()
        counter = _CountingClient(parser.client)
        parser.client = reasoner.client = counter

        start = time.perf_counter()
        ok, detail = True, ""
        try:
            spec = parser.parse(prompt)
            ir = reasoner.generate(spec)
            detail = f"{len(ir.components)} components, {len(ir.connections)} connections"
        except CircuitGenerationError as exc:
            ok, detail = False, exc.attempt_errors[-1][:120]
        except Exception as exc:  # provider errors are results too
            ok, detail = False, f"{type(exc).__name__}: {str(exc)[:100]}"
        elapsed = time.perf_counter() - start

        results.append({"prompt": prompt, "ok": ok, "calls": counter.calls, "seconds": elapsed, "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {elapsed:6.1f}s  calls={counter.calls}  {prompt}")
    return results


def to_markdown(results: list[dict]) -> str:
    passed = [r for r in results if r["ok"]]
    lat = [r["seconds"] for r in passed] or [0.0]
    lines = [
        f"# Circuit OS benchmark — `{settings.ai_model}`",
        "",
        f"- Provider: `{settings.ai_provider}`"
        + (f" (`{settings.openai_base_url}`)" if settings.ai_provider == "openai_compat" else ""),
        f"- GPU: {_gpu_name()}",
        f"- Host: {platform.node()} · Python {platform.python_version()}",
        f"- Valid IR: **{len(passed)}/{len(results)}**",
        f"- Median latency (passing): **{statistics.median(lat):.1f}s**",
        f"- Model calls per design (incl. intent parse + retries): "
        f"**{statistics.mean(r['calls'] for r in results):.1f}**",
        "",
        "| Prompt | Result | Calls | Seconds | Detail |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['prompt']} | {'✅' if r['ok'] else '❌'} | {r['calls']} | {r['seconds']:.1f} | {r['detail']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write a markdown report here")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")  # Windows consoles can't print ✅

    report = to_markdown(run())
    print("\n" + report)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
