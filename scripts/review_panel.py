#!/usr/bin/env python3
"""Explanation review panel — an automated pre-screen for criterion 12.

    python scripts/review_panel.py captures/arduino-reads-dht22__...json

WHAT THIS MEASURES, AND WHAT IT DOES NOT
    It does NOT close criterion 12. An LLM reading LLM output fills gaps from
    training: show it "R1 is a 10k pull-up on DATA" and nothing else, and it
    will still tell you the line never reaches logic HIGH without one — because
    it read a thousand datasheets, not because your explanation said so. A
    descriptive explanation and a consequential one score identically on a naive
    agent panel, and the difference between those two IS the product claim.

    So this measures something else, which a human panel cannot cheaply give
    you: whether the explanation is LOAD-BEARING.

THE ABLATION
    Arm A: reviewers see the explanation only.
    Arm B: reviewers see the schematic and BOM only — no explanation.

    Both answer the same rubric. If B scores as well as A, the explanation added
    nothing a competent reader couldn't already reconstruct. The A−B gap is the
    number to watch, and to track as explainer.py's system prompt changes.

    Every reviewer must also tag each rubric row FROM_TEXT or PRIOR_KNOWLEDGE.
    Only FROM_TEXT rows count toward arm A. That tag is the whole instrument:
    without it the panel grades the model's education rather than your writing.

WHY THE REVIEWERS HAVE NO TOOLS
    Deliberate. A reviewer that can fetch the DHT22 datasheet is more
    contaminated than one working from memory, and it raises the arm-B baseline
    with knowledge no reader of your page would have had. Sandbox them. The
    isolation is the experiment.

WHY THREE DIFFERENT PERSONAS AND NOT THREE COPIES
    Redundancy catches noise; diversity catches failure modes. The junior is the
    actual criterion-12 target. The controls engineer asks what fails in the
    field. The fault-finder is told to hunt for errors rather than to grade — it
    is the only one that can tell you the explanation is confidently wrong,
    which is worth more than any score here.
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from ai.client import ai_model, make_client  # noqa: E402


# ── Rubric ───────────────────────────────────────────────────────────────────
# The two rows marked criterion=True are the criterion. The rest are things a
# competent engineer recovers from the schematic alone, so they cannot
# distinguish a descriptive explanation from a consequential one.
RUBRIC = [
    {"id": "pullup_purpose",
     "ask": "What the pull-up resistor on the sensor data line is for",
     "criterion": False},
    {"id": "missing_pullup_consequence",
     "ask": "What specifically fails if that pull-up is absent — the mechanism, "
            "not just 'it won't work'",
     "criterion": True},
    {"id": "wrong_value_consequence",
     "ask": "What happens if that resistor's value is wrong in either direction",
     "criterion": True},
    {"id": "component_selection",
     "ask": "Why this sensor rather than an alternative, in terms of this "
            "specific requirement",
     "criterion": False},
    {"id": "threshold_implementation",
     "ask": "Where the temperature threshold lives and what the firmware does "
            "when it is crossed",
     "criterion": False},
]

PERSONAS = {
    "junior_ee": (
        "You are a final-year electrical engineering student. You know circuit "
        "fundamentals — Ohm's law, pull-ups, logic levels, open-drain outputs — "
        "but you have never personally built anything with this specific sensor "
        "and you do not have its datasheet. You are the reader this document was "
        "written for."
    ),
    "controls_engineer": (
        "You are a working industrial controls engineer with fifteen years on "
        "HVAC and building automation panels. You are unsentimental about "
        "documentation and you judge it by one question: would this stop a "
        "junior on my team from shipping a board that fails in the field?"
    ),
    "fault_finder": (
        "You are a hardware reviewer whose only job is to find errors. You are "
        "not grading clarity. You are looking for claims that are factually "
        "wrong, numerically impossible, internally contradictory, or asserted "
        "without support. Report what is wrong before you report what is fine."
    ),
}

REVIEW_TOOL = {
    "name": "submit_review",
    "description": "Submit your assessment of the material you were given.",
    "input_schema": {
        "type": "object",
        "properties": {
            "why_each_component": {
                "type": "string",
                "description": "Your answer to: why was each component chosen?",
            },
            "what_would_break": {
                "type": "string",
                "description": "Your answer to: what would break if one were changed?",
            },
            "rubric": {
                "type": "array",
                "description": "One entry per rubric row, in the order given.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "answered": {
                            "type": "boolean",
                            "description": "Can you state this correctly and specifically?",
                        },
                        "source": {
                            "type": "string",
                            "enum": ["from_text", "prior_knowledge", "not_answered"],
                            "description": (
                                "BE STRICT AND HONEST. 'from_text' ONLY if the "
                                "material you were given states it. If you knew it "
                                "already and the material did not say it, that is "
                                "'prior_knowledge' even though your answer is "
                                "correct. This distinction is the entire purpose "
                                "of this review — guessing generously here "
                                "destroys the measurement."
                            ),
                        },
                        "quote": {
                            "type": "string",
                            "description": (
                                "If source is 'from_text', the exact sentence "
                                "that says it. Empty otherwise. If you cannot "
                                "quote it, it is not from_text."
                            ),
                        },
                    },
                    "required": ["id", "answered", "source", "quote"],
                },
            },
            "errors_found": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Statements that are factually wrong, impossible, "
                               "or self-contradictory. Empty if none.",
            },
            "would_a_junior_ship_a_working_board": {
                "type": "boolean",
                "description": "On this material alone, with no other help.",
            },
        },
        "required": ["why_each_component", "what_would_break", "rubric",
                     "errors_found", "would_a_junior_ship_a_working_board"],
    },
}


def rubric_block() -> str:
    return "\n".join(f"  {i + 1}. [{r['id']}] {r['ask']}" for i, r in enumerate(RUBRIC))


def build_prompt(arm: str, capture: dict) -> str:
    resp = capture["response"]
    header = (
        "You are reviewing material for a hardware design. Answer only from what "
        "is in front of you.\n\n"
        "Two questions:\n"
        "  1. Why was each component chosen?\n"
        "  2. What would break if one of them were changed?\n\n"
        "Then fill the rubric. For every row, mark whether the material in front "
        "of you states it ('from_text', with the exact quote) or whether you know "
        "it from your own training and the material did not say it "
        "('prior_knowledge'). Answering correctly from your own knowledge is "
        "'prior_knowledge', not 'from_text'. Be strict: an approximate paraphrase "
        "you cannot quote is not from_text.\n\n"
        f"Rubric rows:\n{rubric_block()}\n\n"
    )

    if arm == "A":
        body = "── THE MATERIAL ──\n\n" + (resp.get("explanation") or "")
    else:
        # Arm B: the circuit itself, no prose. This is the contamination
        # baseline — whatever a reader reconstructs here, the explanation did
        # not contribute.
        ir = resp.get("ir", {})
        parts = ["── THE MATERIAL (schematic data and BOM — no written explanation) ──\n"]
        parts.append("Components:")
        for c in ir.get("components", []):
            parts.append(
                f"  {c.get('id')}: {c.get('type')} {c.get('part_number','')} "
                f"value={c.get('value')} package={c.get('package')}"
            )
        parts.append("\nConnections:")
        for cn in ir.get("connections", []):
            parts.append(f"  {cn.get('component_id')}.{cn.get('pin')} -> {cn.get('node_id')}")
        parts.append("\nNets:")
        for n in ir.get("nodes", []):
            parts.append(f"  {n.get('id')}: type={n.get('type')} v={n.get('voltage_nominal')}")
        parts.append(f"\nIntent: {ir.get('intent','')}")
        body = "\n".join(parts)

    return header + body


def run_reviewer(client, model: str, persona_key: str, arm: str,
                 capture: dict, temperature: float) -> dict | None:
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=temperature,
            system=PERSONAS[persona_key],
            tools=[REVIEW_TOOL],
            tool_choice={"type": "tool", "name": "submit_review"},
            messages=[{"role": "user", "content": build_prompt(arm, capture)}],
        )
    except Exception as e:  # noqa: BLE001
        print(f"    ! {persona_key}/{arm}: {type(e).__name__}: {e}")
        return None

    for block in msg.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input
    print(f"    ! {persona_key}/{arm}: no tool_use in response")
    return None


def score(review: dict) -> dict:
    """Criterion rows credited only when sourced from the text."""
    by_id = {r.get("id"): r for r in review.get("rubric", [])}
    crit = [r["id"] for r in RUBRIC if r["criterion"]]
    from_text = sum(
        1 for cid in crit
        if by_id.get(cid, {}).get("answered") and by_id.get(cid, {}).get("source") == "from_text"
    )
    answered = sum(1 for cid in crit if by_id.get(cid, {}).get("answered"))
    return {"from_text": from_text, "answered_any_source": answered, "of": len(crit)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", help="JSON from scripts/capture_explanation.py")
    ap.add_argument("--samples", type=int, default=3,
                    help="runs per persona per arm (default 3; LLM answers vary)")
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    capture = json.loads(Path(args.capture).read_text(encoding="utf-8"))
    expl = capture["response"].get("explanation") or ""
    if not expl.strip():
        sys.exit("Capture has an empty explanation — nothing to review.")

    client, model = make_client(), ai_model()
    print(f"  capture      : {args.capture}")
    print(f"  written by   : {capture.get('model')}")
    print(f"  reviewed by  : {model}")
    print(f"  explanation  : {len(expl.split())} words")
    print(f"  panel        : {len(PERSONAS)} personas x 2 arms x {args.samples} samples "
          f"= {len(PERSONAS) * 2 * args.samples} calls\n")

    results = defaultdict(list)
    all_errors, raw = [], []

    for persona in PERSONAS:
        for arm in ("A", "B"):
            for s in range(args.samples):
                r = run_reviewer(client, model, persona, arm, capture, args.temperature)
                if r is None:
                    continue
                sc = score(r)
                results[(persona, arm)].append(sc)
                raw.append({"persona": persona, "arm": arm, "sample": s,
                            "score": sc, "review": r})
                if arm == "A":
                    all_errors.extend(r.get("errors_found") or [])
            got = results[(persona, arm)]
            if got:
                mean = statistics.mean(x["from_text"] for x in got)
                print(f"  {persona:<18} arm {arm}: from_text {mean:.2f}/{got[0]['of']}")

    def arm_mean(arm, key="from_text"):
        vals = [x[key] for (p, a), lst in results.items() if a == arm for x in lst]
        return statistics.mean(vals) if vals else 0.0

    a_ft, b_ft = arm_mean("A"), arm_mean("B")
    a_any, b_any = arm_mean("A", "answered_any_source"), arm_mean("B", "answered_any_source")

    print("\n" + "=" * 66)
    print("  Arm A — explanation only     from_text {:.2f} | any source {:.2f}".format(a_ft, a_any))
    print("  Arm B — schematic only       from_text {:.2f} | any source {:.2f}".format(b_ft, b_any))
    print("  " + "-" * 62)
    print(f"  LOAD-BEARING GAP (A−B, any source): {a_any - b_any:+.2f}")
    if a_any - b_any < 0.5:
        print("  ^ Reviewers did about as well WITHOUT the explanation. On this")
        print("    circuit the prose is not carrying the understanding — that is")
        print("    the finding, not a broken script.")
    if a_ft < 1.5:
        print(f"  ^ Only {a_ft:.2f} of 2 criterion rows were traceable to a quote.")
        print("    Correct answers sourced to prior_knowledge mean the reader")
        print("    already knew it. Criterion 12 is at risk.")
    if all_errors:
        print(f"\n  FACTUAL PROBLEMS RAISED ({len(all_errors)}) — worth more than any score:")
        for e in dict.fromkeys(all_errors):
            print(f"    - {e}")
    print("=" * 66)
    print("\n  This is a pre-screen. Criterion 12 still needs a human — see")
    print("  CRITERION_12_REVIEW.md for why an agent cannot close it.")

    out = Path(args.out) if args.out else Path(args.capture).with_suffix(".review.json")
    out.write_text(json.dumps({
        "capture": args.capture,
        "written_by": capture.get("model"),
        "reviewed_by": model,
        "samples": args.samples,
        "summary": {"arm_a_from_text": a_ft, "arm_b_from_text": b_ft,
                    "arm_a_any": a_any, "arm_b_any": b_any,
                    "load_bearing_gap": a_any - b_any},
        "errors_found": list(dict.fromkeys(all_errors)),
        "raw": raw,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  -> {out}")


if __name__ == "__main__":
    main()
