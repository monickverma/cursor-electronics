"""probe_limits.py — measure Jev's tokeniser rate and request-size limits with a few probe calls.

Docs (models page, fetched 2026-09-24): "64k tokens per request; 32k tokens for `state` plus the
longest question"; Choice <= 255 options; Score <= 10 levels. These probes check the documented
numbers against the live API and find how a size rejection looks. All calls are logged via jevcall.

Usage: python probe_limits.py calib|state|total|count
"""
import asyncio
import json
import pathlib
import re
import sys

from jevcall import Budget, call, make_client, SECRET_PATTERNS, MAX_CONCURRENCY

P2 = pathlib.Path("/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2")
Q1 = {"probe": {"type": "noul", "instructions": "Does the state mention an RC low-pass filter?"}}


def filler():
    t = (P2 / "PRODUCT_MASTER.md").read_text(encoding="utf-8")
    for p in SECRET_PATTERNS:
        t = p.sub("[redacted]", t)
    return t


def text_of_chars(n):
    base = filler()
    out = (base + "\n\n") * (n // len(base) + 1)
    return out[:n]


async def main(mode):
    budget = Budget()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    async with make_client() as c:
        if mode == "calib":
            # tiny state -> question overhead; 10k/40k chars of repo prose -> chars per token
            for n in (1, 10_000, 40_000):
                st = "x" if n == 1 else text_of_chars(n)
                r = await call(c, sem, budget, st, Q1, phase="probe_calib", variant=f"chars_{n}",
                               meta={"state_chars": len(st)})
                print(n, r.get("ok"), r.get("usage"), r.get("error", "")[:200])
        elif mode.startswith("state"):
            # state-size probes: args are token targets using the measured chars/token
            cpt = float(mode.split(":")[1])
            for tok in [int(x) for x in mode.split(":")[2].split(",")]:
                st = text_of_chars(int(tok * cpt))
                r = await call(c, sem, budget, st, Q1, phase="probe_state_limit", variant=f"target_{tok}",
                               meta={"target_tokens": tok, "state_chars": len(st)})
                print(tok, r.get("ok"), r.get("usage"), r.get("status"), str(r.get("error", ""))[:300])
        elif mode.startswith("total"):
            # total-size probe: moderate state + many medium questions pushing the 64k request budget
            cpt = float(mode.split(":")[1])
            state_tok, q_tok_total = [int(x) for x in mode.split(":")[2].split(",")]
            st = text_of_chars(int(state_tok * cpt))
            chunk = text_of_chars(int(900 * cpt))  # ~900-token instructions per question
            nq = max(1, q_tok_total // 900)
            qs = {f"q{i:03d}": {"type": "noul", "instructions": f"Q{i}: Does this passage, repeated here for reference, "
                                f"describe the same product as the state? Passage: {chunk}"} for i in range(nq)}
            r = await call(c, sem, budget, st, qs, phase="probe_total_limit",
                           variant=f"state{state_tok}_q{q_tok_total}",
                           meta={"state_tokens_target": state_tok, "question_tokens_target": q_tok_total, "nq": nq})
            print(state_tok, q_tok_total, nq, r.get("ok"), r.get("usage"), r.get("status"), str(r.get("error", ""))[:300])
        elif mode.startswith("count"):
            # question-count probe: tiny state, N tiny Nouls
            for n in [int(x) for x in mode.split(":")[1].split(",")]:
                qs = {f"n{i:04d}": {"type": "noul", "instructions": f"Is {i} an even number?"} for i in range(n)}
                r = await call(c, sem, budget, "Numbers are given in the questions.", qs,
                               phase="probe_question_count", variant=f"n_{n}", meta={"n_questions": n})
                ans = r.get("answers") or {}
                print(n, r.get("ok"), r.get("usage"), r.get("status"), str(r.get("error", ""))[:300],
                      "answers:", len(ans))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
