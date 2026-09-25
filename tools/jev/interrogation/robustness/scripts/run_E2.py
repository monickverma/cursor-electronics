"""run_E2.py - determinism schedule for the fixed 20-question request (items/E2_determinism.json).

Usage: python run_E2.py now_seq | now_conc8 | later_seq | aliases
  now_seq    10 identical requests, one after another (concurrency 1)
  now_conc8  10 identical requests at concurrency 8
  later_seq  10 identical requests, one after another, >= 1 h after now_seq
  aliases    3 each under jev-latest and jev-preview (sequential)
"""
import asyncio
import json
import pathlib
import sys

import jevlog

ITEMS = pathlib.Path(__file__).resolve().parents[1] / "items" / "E2_determinism.json"


async def main(phase: str):
    jevlog.verify_prereg(ITEMS)
    d = json.loads(ITEMS.read_text(encoding="utf-8"))
    r = d["requests"][0]
    runs = {"now_seq": [(jevlog.PINNED, 10, 1)], "now_conc8": [(jevlog.PINNED, 10, 8)],
            "later_seq": [(jevlog.PINNED, 10, 1)],
            "aliases": [("jev-latest", 3, 1), ("jev-preview", 3, 1)]}[phase]
    for model, n, conc in runs:
        async with jevlog.Jev(concurrency=conc) as j:
            rows = await asyncio.gather(*(j.ask(d["experiment"], f"{phase}#{i}", r["item_id"], r["state"],
                                                 r["questions"], model=model) for i in range(n)))
        errs = [x["error"] for x in rows if x["error"]]
        print(phase, model, "n", n, "errors", len(errs), "resolved", {x.get("model_resolved") for x in rows},
              "latency_ms", sorted(x["latency_ms"] for x in rows))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
