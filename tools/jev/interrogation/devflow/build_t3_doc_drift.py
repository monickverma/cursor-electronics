"""T3 doc drift: prose paragraphs from the phase2-stage0 snapshot (p2) paired with derived facts.

Every paragraph is real text from p2 (e803a99); `seeded` and `corrected` items are minimal, recorded edits of a
real paragraph. Facts come from state.json / progress.yaml (derived, generated_from_commit 1126d15), the code
(VERSION constants, data/mcu_targets.py, tests/ listing, file existence) and `git tag`.

Label (contradicts) by construction, relative to the facts excerpt shipped with the item:
  real        True   a real paragraph that asserts as current something the excerpt contradicts
  seeded      True   a consistent real paragraph with one fact edited to contradict the excerpt
  consistent  False  the excerpt agrees (incl. `corrected` edits of the real contradictions)
  dated       False  the differing number is explicitly dated or the document is the frozen snapshot
                     (AGENTS.md: "a snapshot document ... where a frozen number is the point")
  irrelevant  False  the excerpt does not address the paragraph
`implicit` marks real items whose contradiction is carried by a status mark or a to-do rather than a number.
"""
import json
import os
import re

from common import P2, SETS, git, secret_findings, write_jsonl

ROLE = {
    "MENTAL_MODEL.md": "Root prose overview: what is real, what is unverified, what is only roadmap. Header says "
                       "'Last updated: 2026-08-22'.",
    "ROADMAP.md": "Root prose: what to do next, in order. Header says 'Last updated: 2026-08-22 · commit 36923cf'.",
    "PHASE1_COMPLETE.md": "Snapshot document frozen at the v0.1.0 tag (2026-08-25). AGENTS.md: 'The exception is a "
                          "snapshot document — PHASE1_COMPLETE.md — where a frozen number is the point.'",
    ".claude/rules/testing.md": "Rules file for writing and running tests (agent instructions).",
    "docs/BENCH_D1.md": "Bench sheet for defeater D1: the procedure for a hardware check of the designs the "
                        "generators produce today.",
    ".claude/shared-memory/brain/vision.md": "LAYER 1 vision summary; manual, rarely changes.",
    ".claude/shared-memory/brain/architecture.md": "LAYER 2 architecture; manual, updated when the architecture "
                                                   "changes.",
    ".claude/shared-memory/brain/knowledge.md": "LAYER 5 domain facts; manual, append-only.",
    ".claude/shared-memory/brain/timeline.md": "LAYER 6 history; dated, append-only entries.",
    ".claude/shared-memory/SETUP.md": "How to load the shared memory into a new assistant session.",
    ".claude/shared-memory/AGENTS.md": "Agent bootstrap rules.",
    ".claude/CLAUDE.md": "Agent instructions; the owner of the project file tree.",
    ".claude/shared-memory/plan/master_plan.md": "Summary of the full roadmap.",
    "README.md": "Public README.",
}


def text_of(rel):
    return (P2 / rel).read_text(encoding="utf-8")


def paras(rel):
    return [p.strip() for p in re.split(r"\n\s*\n", text_of(rel)) if p.strip()]


def para(rel, *idx):
    ps = paras(rel)
    return "\n\n".join(ps[i] for i in idx)


def para_with(rel, needle):
    hits = [p for p in paras(rel) if needle in p]
    assert len(hits) == 1, (rel, needle, len(hits))
    return hits[0]


def section_of(rel, snippet):
    t = text_of(rel)
    pos = t.find(snippet[:60])
    assert pos >= 0, (rel, snippet[:60])
    heads = [m for m in re.finditer(r"(?m)^#{1,4} .+$", t) if m.start() <= pos]
    return heads[-1].group(0) if heads else ""


def edit(text, old, new):
    assert old in text, (old, text[:120])
    return text.replace(old, new, 1)


# ------------------------------------------------------------------ derived facts
def load_facts():
    st = json.loads(text_of(".claude/shared-memory/state.json"))
    prog = text_of(".claude/shared-memory/progress.yaml")
    summ = dict(re.findall(r"(?m)^  (entries_total|entries_verified_done|entries_untested|pct_verified): ([\d.]+)",
                           prog))

    def module_status(name):
        m = re.search(r"(?ms)^  " + re.escape(name) + r":\n(.*?)(?=^  \S)", prog)
        block = m.group(1) if m else ""
        tf = re.search(r"test_file_status: (\S+)", block)
        ms = re.search(r"module_status: (\S+)", block)
        return {"module_status": ms.group(1) if ms else None, "test_file_status": tf.group(1) if tf else None}

    versions = {}
    for f in sorted((P2 / "backend/generators").glob("*.py")):
        m = re.search(r'(?m)^VERSION = "([^"]+)"', f.read_text(encoding="utf-8"))
        if m:
            versions[f.stem] = m.group(1)
    boards = [f"{i} ({b}, {m})" for i, b, m in re.findall(
        r'id="([a-z0-9_]+)", board="([^"]+)", mcu_part="([^"]+)"', text_of("backend/data/mcu_targets.py"))]
    wf = re.search(r"(?ms)^      waveforms_from:\n.*?description: (.+?)\n", prog)
    phase = {k: v for k, v in st["phase"].items() if k != "phase1_criteria_deferred"}
    crit = {str(i): c for i, c in enumerate(st["phase1_criteria"], 1) if i in (11, 12)}
    return {
        "test_summary": {**st["test_summary"], "source": "state.json, generated_from_commit "
                                                          + st["generated_from_commit"]},
        "phase": {**phase, "source": "state.json"},
        "phase1_criteria_11_12": {**crit, "legend": st["phase1_criteria_legend"], "source": "state.json"},
        "generator_versions": {**versions, "source": "VERSION constants in backend/generators/*.py"},
        "progress_summary": {**{k: float(v) if "." in v else int(v) for k, v in summ.items()},
                             "source": "progress.yaml summary"},
        "boards": {"firmware_targets": boards,
                   "note": "each target's firmware is compiled with PlatformIO before it is shown",
                   "source": "backend/data/mcu_targets.py; generators/firmware/compile_gate.py"},
        "waveforms_module": {"simulation/waveforms": {**module_status("simulation/waveforms"),
                                                      "waveforms_from": wf.group(1).strip("'\" ") if wf else None},
                             "source": "progress.yaml"},
        "ai_modules": {"registered_ai_modules": sorted(k for k in st["modules"] if k.startswith("ai/")),
                       "backend/ai/circuit_reasoner.py": "does not exist" if not (P2 / "backend/ai/circuit_reasoner.py").exists() else "exists",
                       "source": "state.json modules; file system"},
        "llm_scanner_test": {"tests/test_llm_cannot_write_circuit_ir.py": "passing (in the 2001-pass suite)",
                             "source": "state.json test_summary; tests/ listing"},
        "accuracy_test": {"tests/test_simulation_accuracy.py": "exists; part of the passing suite",
                          "criterion_11": crit["11"], "source": "tests/ listing; state.json"},
        "test_modules": {"tests/test_*.py modules": len(list((P2 / "tests").glob("test_*.py"))),
                         "source": "tests/ directory listing"},
        "git_tags": {"tags": git("tag", "-l").split(), "source": "git tag"},
        "blockers": {"blockers": st["blockers"], "source": "state.json"},
        "grade_floors": {"library_grade_floor": st["validation"]["grade_floor"],
                         "per_generator": {g: v["grade_floor"] for g, v in st["validation"]["generators"].items()},
                         "open_defeaters": {k: len(v) for k, v in st["validation"]["open_defeaters"].items()},
                         "source": "state.json validation"},
    }


F = None


def facts(*keys):
    return {k: F[k] for k in keys}


ITEMS = []


def add(iid, typ, label, doc, paragraph, keys, note, implicit=False, section=None, edit_rec=None):
    ITEMS.append({"task": "T3", "item_id": f"T3-{iid}", "type": typ, "label": label, "implicit": implicit,
                  "doc": doc, "construction": note, "edit": edit_rec,
                  "state": {"document": doc, "document_role": ROLE[doc],
                            "section": section if section is not None else section_of(doc, paragraph.split("\n")[0]),
                            "paragraph": paragraph, "derived_facts": facts(*keys)}})


def build():
    global F
    F = load_facts()
    MM, RM, TM, BD = "MENTAL_MODEL.md", "ROADMAP.md", ".claude/rules/testing.md", "docs/BENCH_D1.md"
    VI, AR = ".claude/shared-memory/brain/vision.md", ".claude/shared-memory/brain/architecture.md"
    PC, CL, MP = "PHASE1_COMPLETE.md", ".claude/CLAUDE.md", ".claude/shared-memory/plan/master_plan.md"
    bench = para_with(BD, "The designs are what the generators produce today")
    t9 = para(TM, 9)
    claude_line = next(l for l in text_of(CL).splitlines() if "test modules + fixtures" in l).strip()
    mp_table = "\n".join(l for l in text_of(MP).splitlines()
                         if l.startswith("| Phase |") or l.startswith("|---") and "Timeline" not in l
                         or re.match(r"^\| [1-5] \|", l))
    mp_table = "\n".join(dict.fromkeys(mp_table.splitlines()))
    mp_section = "## Phase Overview (from PRODUCT_MASTER.md Part 6)"

    # ---------------- real contradictions
    add("R01", "real", True, TM, t9, ["test_summary"], "171 passed / 24 skipped vs derived 2001 / 30")
    add("R02", "real", True, BD, bench, ["generator_versions"], "led_indicator 0.1.1 vs code 0.2.0")
    add("R03", "real", True, MM, para(MM, 35), ["phase"], "'Phase 2 has not started' vs phase.current 2 in_progress")
    add("R04", "real", True, MM, para(MM, 38), ["phase1_criteria_11_12", "phase"],
        "criterion 11 '⏳ ... not yet written' vs ✅* met_by_substitute; 12 '⏳' vs '⏭' deferred")
    add("R05", "real", True, MM, para(MM, 28, 29), ["boards", "waveforms_module"],
        "'Does not exist: ESP32/STM32 firmware, waveform graphs' vs three board targets and a verified waveforms module")
    add("R06", "real", True, MM, para(MM, 19, 20), ["ai_modules"],
        "'Prompt → DesignSpec → CircuitIR (3-attempt retry)' vs circuit_reasoner.py gone, intent_producer present")
    add("R07", "real", True, MM, para(MM, 74), ["accuracy_test"],
        "to-do 'Write tests/test_simulation_accuracy.py ... Closes criterion 11' vs file exists, criterion met_by_substitute",
        implicit=True)
    add("R08", "real", True, RM, para(RM, 5), ["phase"], "'Phase 1 is nearly done' vs phase1 closed_with_deferral, phase 2 current")
    add("R09", "real", True, CL, claude_line, ["test_modules"], "'12 test modules' vs 42 test_*.py modules",
        section="## Project Structure")
    add("R10", "real", True, MP, mp_table, ["phase"], "Phase 1 '🔄 10/12', Phase 2 '⬜ Not started' vs 11/12 closed, phase 2 in progress",
        section=mp_section)
    add("R11", "real", True, TM, para(TM, 22, 23, 24), ["phase1_criteria_11_12"],
        "accuracy gate 'cannot be automated ... within 15% of bench' vs criterion 11 = closed-form ≤2%, met_by_substitute",
        implicit=True)
    add("R12", "real", True, RM, para(RM, 16, 17), ["git_tags", "phase"],
        "Step 3 'Tag v0.1.0 ... ⬜' (not done) vs tag v0.1.0 exists and phase 1 closed", implicit=True)

    # ---------------- seeded contradictions (one edit of a consistent real paragraph)
    def seed(iid, doc, base, old, new, keys, note, section=None):
        add(iid, "seeded", True, doc, edit(base, old, new), keys, note,
            section=section if section is not None else section_of(doc, base.split("\n")[0]),
            edit_rec={"old": old, "new": new})
    seed("S01", RM, para(RM, 26), "Marked `met_by_substitute`, not `met`", "Marked `met`, not a substitute",
         ["phase1_criteria_11_12"], "criterion 11 said met outright")
    seed("S02", BD, edit(bench, "led_indicator 0.1.1", "led_indicator 0.2.0"), "rc_lowpass 0.2.3", "rc_lowpass 0.2.1",
         ["generator_versions"], "rc_lowpass 0.2.1 vs 0.2.3 (led corrected first)")
    seed("S03", VI, para(VI, 18), "the current phase is Phase 2", "the current phase is Phase 3", ["phase"],
         "current phase 3 vs 2")
    seed("S04", AR, para(AR, 14), "Placement and `api/routes/pcb` are tested; routing is not.",
         "Placement, routing and `api/routes/pcb` are all tested.", ["blockers"], "routing tested vs blocker 'PCB routing untested'")
    seed("S05", RM, para(RM, 17), "v0.1.0 tags at **11 of 12**", "v0.1.0 tags at **12 of 12**", ["phase"],
         "12 of 12 vs 11 of 12")
    seed("S06", AR, para(AR, 6), "**The LLM only ever writes IntentIR — a requirement. A deterministic generator\nwrites the CircuitIR.**",
         "**The LLM writes the CircuitIR directly through `ai/circuit_reasoner.py`, retrying\nup to three times.**",
         ["ai_modules", "llm_scanner_test"], "LLM writes CircuitIR via circuit_reasoner vs module absent")
    seed("S07", TM, edit(t9, "**171 passed, 24 skipped** (24 skipped", "**2001 passed, 30 skipped** (30 skipped"),
         "**2001 passed, 30 skipped**", "**2001 passed, 3 failed, 30 skipped**", ["test_summary"], "3 failed vs 0 failed",
         section=section_of(TM, t9.split("\n")[0]))
    tl = para_with(".claude/shared-memory/brain/timeline.md", "every LED grid design on every board is G1")
    seed("S08", ".claude/shared-memory/brain/timeline.md", tl, "every LED grid design on every board is G1",
         "every LED grid design on every board is G2", ["grade_floors"], "LED designs G2 vs led_indicator floor G1")
    seed("S09", RM, para(RM, 21), "Phase 2 is the Validation Engine.", "Phase 2 is the Industrial Layer.", ["phase"],
         "phase 2 name")
    seed("S10", BD, edit(bench, "led_indicator 0.1.1", "led_indicator 0.2.0"), "voltage_divider 0.1.0",
         "voltage_divider 0.2.0", ["generator_versions"], "voltage_divider 0.2.0 vs 0.1.0 (led corrected first)")
    seed("S11", VI, para(VI, 18), "(closed 2026-08-25;", "(closed 2026-08-25 at 12 of 12 criteria;", ["phase"],
         "12 of 12 vs 11/12")

    # ---------------- consistent controls (real paragraphs, and corrected versions of the real contradictions)
    add("C01", "consistent", False, RM, para(RM, 26), ["phase1_criteria_11_12"], "criterion 11 met_by_substitute, as derived")
    add("C02", "consistent", False, AR, para(AR, 6), ["ai_modules", "llm_scanner_test"], "LLM writes IntentIR only")
    add("C03", "consistent", False, AR, para(AR, 14), ["blockers"], "routing untested, as the blocker says")
    add("C04", "consistent", False, VI, para(VI, 18), ["phase"], "phase 1 closed, current phase 2")
    add("C05", "consistent", False, PC, para(PC, 1), ["phase", "phase1_criteria_11_12"], "11 of 12, 11 by substitute")
    add("C06", "consistent", False, RM, para(RM, 17), ["phase", "git_tags"], "v0.1.0 at 11 of 12")
    c7 = edit(t9, "**171 passed, 24 skipped** (24 skipped", "**2001 passed, 30 skipped** (30 skipped")
    add("C07", "consistent", False, TM, c7, ["test_summary"], "R01 corrected to the derived counts",
        section=section_of(TM, t9.split("\n")[0]), edit_rec={"old": "171 passed, 24 skipped (24", "new": "2001 passed, 30 skipped (30"})
    add("C08", "consistent", False, BD, edit(bench, "led_indicator 0.1.1", "led_indicator 0.2.0"), ["generator_versions"],
        "R02 corrected", edit_rec={"old": "led_indicator 0.1.1", "new": "led_indicator 0.2.0"})
    add("C09", "consistent", False, MM, "Phase 2 is in progress.", ["phase"], "R03 corrected",
        section="## 5. Where The Project Actually Stands",
        edit_rec={"old": "Phase 2 has not started.", "new": "Phase 2 is in progress."})
    add("C10", "consistent", False, CL, claude_line.replace("12 test modules", "42 test modules"), ["test_modules"],
        "R09 corrected", section="## Project Structure", edit_rec={"old": "12 test modules", "new": "42 test modules"})
    mp_fixed = mp_table.replace("🔄 10/12 criteria done", "✅ closed at 11/12 criteria").replace(
        "| 2 | Validation Engine | Months 3–8 | ⬜ Not started |", "| 2 | Validation Engine | Months 3–8 | 🔄 In progress |")
    assert mp_fixed != mp_table
    add("C11", "consistent", False, MP, mp_fixed, ["phase"], "R10 corrected", section=mp_section,
        edit_rec={"old": "10/12 / Not started", "new": "closed 11/12 / In progress"})
    add("C12", "consistent", False, RM, para(RM, 21), ["phase"], "Phase 2 is the Validation Engine")
    add("C13", "consistent", False, MM, para(MM, 26), ["blockers"], "routing quality untested")
    add("C14", "consistent", False, RM, para(RM, 3), ["test_summary"], "pointer: counts live in state.json")
    add("C15", "consistent", False, ".claude/shared-memory/brain/timeline.md", tl, ["grade_floors"],
        "LED designs G1 = led_indicator floor G1")
    add("C16", "consistent", False, "README.md", para_with("README.md", "400+ passing tests"), ["test_summary"],
        "'400+ passing tests' is true of 2001 (a naive number regex flags it)")

    # ---------------- dated / snapshot controls
    kn = ".claude/shared-memory/brain/knowledge.md"
    add("D01", "dated", False, kn, para_with(kn, "257 passed, 24 skipped, 0 failing") + "\n\n"
        + para_with(kn, "That figure is a 2026-08-07 snapshot"), ["test_summary"], "dated 2026-08-07 snapshot, says so")
    su = ".claude/shared-memory/SETUP.md"
    add("D02", "dated", False, su, para_with(su, "257 tests pass, 10/12 Phase 1 criteria done (as of 2026-08-07)"),
        ["test_summary", "phase"], "'as of 2026-08-07'")
    add("D03", "dated", False, PC, para(PC, 12), ["test_summary"], "snapshot document, commit-stamped count")
    add("D04", "dated", False, PC, para(PC, 34, 35), ["boards", "waveforms_module"],
        "snapshot document's 'what does not exist' at the v0.1.0 tag")
    add("D05", "dated", False, MM, para(MM, 44, 45), ["progress_summary"], "'On 2026-08-07 the verified figure went ...'")
    ag = ".claude/shared-memory/AGENTS.md"
    add("D06", "dated", False, ag, para_with(ag, "reported 318 tests and"), ["test_summary", "phase"],
        "history of a past drift")
    add("D07", "dated", False, VI, para(VI, 21, 22), ["phase", "phase1_criteria_11_12"], "'10 of 12 done as of 2026-06-02'")
    add("D08", "dated", False, RM, para(RM, 56), ["progress_summary"], "'reported 84.4% verified' (past)")

    # ---------------- irrelevant controls
    add("X01", "irrelevant", False, MM, para(MM, 4), ["test_summary"], "one-sentence pitch vs test counts")
    add("X02", "irrelevant", False, MM, para(MM, 68), ["generator_versions"], "explanation examples vs versions")
    add("X03", "irrelevant", False, VI, para(VI, 9), ["phase"], "what the product is not vs phase")
    add("X04", "irrelevant", False, MM, para(MM, 55), ["test_summary"], "pitfalls vs test counts")
    add("X05", "irrelevant", False, RM, para(RM, 48), ["generator_versions"], "free-form caution vs versions")
    add("X06", "irrelevant", False, MM, para(MM, 61), ["test_summary"], "competitive position vs test counts")

    for it in ITEMS:
        it["det_naive"] = det(it, dated_aware=False)
        it["det_dated"] = det(it, dated_aware=True)
        assert not secret_findings(it["state"]), it["item_id"]
    return ITEMS


# ------------------------------------------------------------------ deterministic baselines
GENS = "rc_lowpass|voltage_divider|led_indicator|dht22_node|rs485_node"
DATED = re.compile(r"\d{4}-\d{2}-\d{2}|as of|at the last|reported|went \d|carried|snapshot", re.I)


def det(it, dated_aware):
    s, f = it["state"], it["state"]["derived_facts"]
    if dated_aware and it["doc"] == "PHASE1_COMPLETE.md":
        return {"flag": False, "hits": [], "rule": "snapshot document skipped"}
    hits = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", s["paragraph"]):
        if dated_aware and DATED.search(sent):
            continue
        if "generator_versions" in f:
            for g, v in re.findall(rf"({GENS})[ @]v?(\d+\.\d+\.\d+)", sent):
                if f["generator_versions"].get(g) not in (None, v):
                    hits.append(f"{g} {v}")
        if "test_summary" in f:
            ts = f["test_summary"]
            for n in re.findall(r"(\d[\d,]*)\+? (?:passed|passing|tests pass)", sent):
                if int(n.replace(",", "")) != ts["passed"]:
                    hits.append(f"passed {n}")
            for n in re.findall(r"(\d+) skipped", sent):
                if int(n) != ts["skipped"]:
                    hits.append(f"skipped {n}")
            for n in re.findall(r"(\d+) (?:failed|failing)", sent):
                if int(n) != ts["failed"]:
                    hits.append(f"failed {n}")
        if "phase" in f:
            for n in re.findall(r"(\d+) of 12|(\d+)/12", sent):
                n = int(next(x for x in n if x))
                if n != f["phase"]["phase1_criteria_done"]:
                    hits.append(f"criteria {n}/12")
            for n in re.findall(r"current phase is Phase (\d)", sent):
                if int(n) != f["phase"]["current"]:
                    hits.append(f"phase {n}")
        if "test_modules" in f:
            for n in re.findall(r"(\d+) test modules", sent):
                if int(n) != f["test_modules"]["tests/test_*.py modules"]:
                    hits.append(f"test modules {n}")
        if "progress_summary" in f:
            for n in re.findall(r"(\d+(?:\.\d+)?)% verified", sent):
                if float(n) != f["progress_summary"]["pct_verified"]:
                    hits.append(f"verified {n}%")
    return {"flag": bool(hits), "hits": hits,
            "rule": "number/version regex vs facts" + ("; dated sentences and the snapshot doc skipped" if dated_aware else "")}


if __name__ == "__main__":
    items = build()
    from collections import Counter
    h = write_jsonl(SETS / "t3_doc_drift.jsonl", items)
    print(len(items), Counter((i["type"], i["label"]) for i in items), h)
    for it in items:
        print(it["item_id"], it["type"], it["label"], "naive", it["det_naive"]["flag"], it["det_naive"]["hits"],
              "dated", it["det_dated"]["flag"], len(json.dumps(it["state"])))
