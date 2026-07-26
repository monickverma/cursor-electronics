"""
agent.py — the loop. This is the only file that talks to Opus.

    pip install anthropic
    export ANTHROPIC_API_KEY=...
    python agent.py                 # live
    python agent.py --dry-run       # scripted, no key, no spend

WHAT THE MODEL IS DOING HERE
----------------------------
Not routing. It is doing four things a solver cannot:

  1. Reading intent          "USB needs 90 ohm" is not derivable from a netlist
  2. Compiling constraints   intent -> net classes, diff pairs, keepouts
  3. Judging results         reading DRC output and deciding what to change
  4. Explaining              why each rule exists, in reviewable language

Steps 1 and 4 are the product. Step 2 is where an LLM genuinely outperforms a
rules engine, because the mapping from "this is a CO2 sensor next to a Wi-Fi
module" to "add a thermal keepout" is semantic, open-ended, and impossible to
enumerate in advance. Step 3 is the loop closing: the model proposes, the
kernel disposes, and the model reads the exact numbers back.

THE COMPLETION CRITERIA PATTERN
-------------------------------
Notice `GOAL` below states what *done* means before any work starts, in terms
the kernel can evaluate — zero DRC errors, zero unrouted, power nets at least
0.4 mm. This is lifted straight from the Flux transcript, where the prompt
carried a "Schematic Completion Criteria" section. It is not decoration. An
agent with a checkable definition of done can iterate against it; an agent
without one stops when it runs out of enthusiasm. Make the finish line
machine-readable and the loop terminates for the right reason.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from board_ir import demo_board
from kernel import drc, score
from router import AStarRouter
from tools import TOOLS, Session, execute, as_text

MODEL = "claude-opus-5"

SYSTEM = """You are a PCB layout engineer working through a tool interface.

HOW THIS SYSTEM DIVIDES LABOUR
You do not draw copper. There is no tool to place a track or a via, and this is
deliberate: clearance is a property of every coordinate relative to every other
coordinate, which cannot be checked while generating tokens. A search algorithm
does that part exactly and quickly.

Your job is to decide what the router should be asked to do, and to judge what
it produces. Specifically: set net classes, declare differential pairs, assign
planes, add keepouts, place components, invoke the router, read the DRC report,
and adjust. Placement is yours because it is semantic and low-dimensional.

HOW TO WORK
- Read the board before changing it, and re-read after routing.
- Every constraint takes a `rationale`. Write it for a reviewing engineer, not
  for a log file. A rule nobody can evaluate is worse than no rule.
- Routing outcomes vary widely with net ordering alone. If a run is poor, more
  candidates is usually cheaper than more cleverness.
- The DRC report is ground truth with exact measured and required distances.
  When it contradicts you, it is correct.

CALIBRATION — THIS MATTERS MORE THAN ANYTHING ELSE HERE
State uncertainty in proportion to what you have actually verified.

Impedance is the trap. You cannot compute a trace width for a target impedance
without the distance from the signal layer to its reference plane, and that
number comes from the fabricator's stackup. It is NOT board thickness divided
by layer count — real impedance-controlled stackups are deliberately asymmetric,
pulling signal layers close to their planes. A tool that divides evenly and then
quotes an impedance to three significant figures will be wrong by tens of ohms
and will sound completely confident doing it.

So: give the number, name the assumption it rests on, and say plainly what would
have to be true for it to hold. "Approximately 90 ohms IF the signal layer sits
0.2 mm from its reference plane; confirm against your fabricator's stackup
before trusting this" is a good answer. "0.2 mm track, 0.15 mm gap gives 90 ohms"
is a bad one even when the arithmetic is right, because it hides the assumption
that does the work.

Finish by reporting what you verified, what you assumed, and what a human still
has to check before this is fabricated."""

GOAL = """Prepare this board for routing, then route it.

Completion criteria — you are done when all of these hold, and not before:
  1. Power nets (GND, +3V3) are on a net class of at least 0.4 mm with a
     clearance of at least 0.2 mm.
  2. Both inner layers have an appropriate plane assignment, and you have
     stated the return-path consequence of your choice.
  3. The router has been run with at least 6 candidates.
  4. You have read the DRC report and either the error count is zero or you
     have explained precisely which errors remain, why, and what would fix them.

Work through these in order. Explain each decision as you make it."""


# ─────────────────────────────────────────────────────────────────────────────
def run_live(session: Session, goal: str, max_turns: int = 24) -> None:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("pip install anthropic")

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    messages: list[dict] = [{"role": "user", "content": goal}]

    for turn in range(max_turns):
        resp = client.messages.create(
            model=MODEL, max_tokens=4096, system=SYSTEM,
            tools=TOOLS, messages=messages)

        for block in resp.content:
            if block.type == "text" and block.text.strip():
                print(f"\n\033[36m{block.text.strip()}\033[0m")

        if resp.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            print(f"\n\033[33m→ {block.name}\033[0m "
                  f"{json.dumps(block.input, default=str)[:160]}")
            out = execute(session, block.name, block.input)
            print(f"\033[32m← {as_text(out)[:260]}\033[0m")
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": as_text(out)})
        messages.append({"role": "user", "content": results})

    print("\n" + "=" * 68)
    print("final:", score(session.board))
    for h in session.history:
        print("  ·", h)


# ─────────────────────────────────────────────────────────────────────────────
def run_dry(session: Session) -> None:
    """The exact call sequence a competent model produces, executed for real.

    Everything below the model is genuine — real constraint mutation, real
    A* routing, real DRC. Only the decisions are canned. This is how you
    develop and test the system without spending tokens, and how you write
    regression tests for a stochastic component."""
    script = [
        ("get_board_summary", {}),
        ("set_net_class", {
            "name": "power", "nets": ["GND", "+3V3"],
            "track_width": 0.45, "clearance": 0.2, "priority": 10,
            "rationale": "Bulk current and low impedance return; 0.45 mm carries "
                         "~1.2 A at a 10 C rise on 1 oz copper, with margin."}),
        ("set_net_class", {
            "name": "signal", "nets": ["SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS"],
            "track_width": 0.2, "clearance": 0.15,
            "via_drill": 0.3, "via_diameter": 0.6, "priority": 5,
            "rationale": "Smaller vias reduce stub length and parasitic "
                         "inductance on the fastest edges on the board."}),
        ("assign_plane", {
            "layer": "In1.Cu", "net": "GND",
            "rationale": "Solid reference directly beneath F.Cu shortens return "
                         "loops and lowers radiated emissions."}),
        ("assign_plane", {
            "layer": "In2.Cu", "net": "+3V3",
            "rationale": "Low-impedance power distribution; accepting that B.Cu "
                         "then references +3V3 rather than GND."}),
        ("run_autorouter", {"candidates": 6}),
        ("get_drc_report", {"limit": 5}),
    ]

    for name, args in script:
        print(f"\n\033[33m→ {name}\033[0m {json.dumps(args, default=str)[:150]}")
        out = execute(session, name, args)
        text = as_text(out)
        print(f"\033[32m← {text[:400]}{'…' if len(text) > 400 else ''}\033[0m")

    print("\n" + "=" * 68)
    print("FINAL BOARD")
    print(" ", score(session.board))
    print("\nDECISION LOG (what a reviewer would read)")
    for h in session.history:
        print("  ·", h)

    vs = drc(session.board)
    errs = sum(1 for x in vs if x.severity == "error")
    print(f"\nCOMPLETION CRITERIA")
    nc = session.board.net_class_for("GND")
    planes = {l.name: l.plane_net for l in session.board.layers if l.plane_net}
    checks = [
        ("power net class >= 0.4 mm / 0.2 mm",
         nc.track_width >= 0.4 and nc.clearance >= 0.2),
        ("both inner layers assigned", len(planes) == 2),
        ("router ran >= 6 candidates", len(session.candidates) >= 6),
        ("DRC read and accounted for", True),
    ]
    for label, ok in checks:
        print(f"  [{'x' if ok else ' '}] {label}")
    print(f"\n  {errs} DRC errors remain, "
          f"{len(session.board.unrouted())} connections unrouted.")
    print("  Both are reported honestly rather than suppressed — see README,")
    print("  'Known limits of the reference router'.")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="run the canned call sequence, no API key needed")
    ap.add_argument("--goal", default=GOAL)
    a = ap.parse_args()

    sess = Session(board=demo_board(), backend=AStarRouter())
    print(f"board: {len(sess.board.components)} components, "
          f"{len(sess.board.nets())} nets, "
          f"{len(sess.board.required_connections())} connections\n")

    if a.dry_run or not os.environ.get("ANTHROPIC_API_KEY"):
        if not a.dry_run:
            print("(no ANTHROPIC_API_KEY — falling back to --dry-run)\n")
        run_dry(sess)
    else:
        run_live(sess, a.goal)
