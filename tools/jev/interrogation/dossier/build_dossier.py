"""build_dossier.py — assemble the Circuit OS "big file" for Jev from repo sources.

Every section carries a stable ID ([S01]..[S31]) and names its sources. Most text is verbatim
from the code/doc snapshot p2 (= origin/phase2-stage0 @ e803a99), the owner's handoff
(HANDOFF_2026-09-25.md), the earlier research report and the first live Jev results; a few
sections are authored tables whose every fact is taken from those sources. Credentials, the
test-account login, e-mail addresses and Windows user paths are scrubbed.

Outputs (next to this file):
  circuit_os_dossier.md        full dossier (original section order)
  circuit_os_dossier_core.md   core dossier (~1/4 size; a subset of sections, verbatim)
  dossier_sections.json        section id -> title, sources, body, core flag (for variants)

Usage: python build_dossier.py
"""
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCRATCH = pathlib.Path("/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad")
P2 = SCRATCH / "p2"
MEM = P2 / ".claude/shared-memory"
HANDOFF = SCRATCH / "HANDOFF_2026-09-25.md"
REPORT = REPO / "reports/Jev decisions for Circuit OS Phase 3.md"
RESULTS = REPO / "tools/jev/RESULTS_2026-09-25.md"
REQ = REPO / "tools/jev/requests"

sys.path.insert(0, str(HERE))
from jevcall import SECRET_PATTERNS  # noqa: E402


def scrub(t):
    t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[e-mail removed]", t)
    t = re.sub(r"(?i)c:[\\/]+users[\\/]+[A-Za-z0-9_.-]+", "[user folder]", t)
    t = re.sub(r"TestPass\w*!?", "[password removed]", t)
    t = t.replace("At KIIT,", "At the owner's university,")
    for p in SECRET_PATTERNS:
        t = p.sub("[removed]", t)
    return t


def L(path, a, b):
    lines = pathlib.Path(path).read_text(encoding="utf-8").split("\n")
    return "\n".join(lines[a - 1:b]).strip("\n")


def demote(t, levels=2):
    """Push markdown headings down so they nest under a section heading."""
    return re.sub(r"^(#{1,4}) ", lambda m: "#" * min(6, len(m.group(1)) + levels) + " ", t, flags=re.M)


SECTIONS = []


def sec(sid, title, sources, body, core=False):
    body = re.sub(r"^(#{1,6}) ", lambda m: "#" * max(4, min(6, len(m.group(1)) + 2)) + " ", body.strip(), flags=re.M)
    SECTIONS.append({"id": sid, "title": title, "sources": sources, "body": scrub(body), "core": core})


def req_state(name):
    return json.loads((REQ / name).read_text(encoding="utf-8"))["state"]


def facts_block(name, extra_facts=()):
    st = req_state(name)
    d = st["decision"]
    out = [f"*Question:* {d['question']}", "*Facts:*"]
    for f in d.get("facts", []):
        if "<PASTE" in f["fact"]:
            continue
        if f["fact"].startswith("Decision log, Stage 3 and Stage 4 (verbatim)"):
            continue
        out.append(f"- {f['fact']}")
    for f in extra_facts:
        out.append(f"- {f}")
    if d.get("options"):
        out.append("*Options on the table:*")
        for o in d["options"]:
            rev = o.get("reversibility", {})
            out.append(f"- `{o['id']}` — {o.get('what_changes', '')} Costs: {o.get('costs', '')}"
                       f"{' Invalidates signatures.' if rev.get('signatures_invalidated') else ''}")
    for x in d.get("excluded_by_rule", []):
        out.append(f"- Excluded by rule: {x['option']} ({x['rule']}).")
    for u in st.get("unknowns", []):
        if "<PASTE" not in u:
            out.append(f"- Unknown: {u}")
    return "\n".join(out)


def load_register():
    spec = importlib.util.spec_from_file_location("defeaters_snapshot", P2 / "backend/validation/defeaters.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = ["| ID | Doubt | Applies to | Status | Eliminated by | Trigger |", "|---|---|---|---|---|---|"]
    for d in mod.REGISTER.values():
        rows.append(f"| {d.id} | {d.doubt} | {d.applies_to} | {d.status} | {d.eliminated_by} | {d.trigger or '—'} |")
    return "\n".join(rows)


def compact(t):
    """Collapse alignment whitespace (tables, trees, code comments) to single spaces."""
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"[│├└─]+", "", t)
    return re.sub(r"\n{3,}", "\n\n", t)


def drop_cols(table, drop):
    out = []
    for line in table.split("\n"):
        if line.startswith("|"):
            cells = line.strip().strip("|").split("|")
            cells = [c for i, c in enumerate(cells) if i not in drop]
            out.append("|" + "|".join(cells) + "|")
        else:
            out.append(line)
    return "\n".join(out)


def J(*parts):
    return "\n\n".join(p for p in parts if p)


DM = MEM / "brain/decisions.md"
CP = MEM / "plan/current_phase.md"


def build():
    SECTIONS.clear()
    # ------------------------------------------------------------------ beginning
    sec("S01", "What Circuit OS is", "HANDOFF §1; PRODUCT_MASTER.md Part 1; brain/vision.md",
        J(L(HANDOFF, 8, 8), L(P2 / "PRODUCT_MASTER.md", 17, 17), L(MEM / "brain/vision.md", 39, 49)), core=True)
    sec("S02", "Rules nothing may break", "HANDOFF §2 (verbatim)", L(HANDOFF, 11, 17), core=True)
    sec("S03", "Process rules, trust hierarchy, one owner per fact", "HANDOFF §3; .claude/shared-memory/AGENTS.md",
        J(L(HANDOFF, 20, 22), "Trust hierarchy (AGENTS.md), highest first: test results + simulation outputs; source "
          "code via AST scan; progress.yaml + state.json (derived); plan/current_phase.md; brain/*.md files; agent-written "
          "prose summaries (lowest).",
          "One owner per fact (AGENTS.md): every drift this project has suffered was a stale copy, not a missing check. "
          "Why a choice was made lives in brain/decisions.md (append-only; the entry is written before the code it "
          "governs). Every new module is registered in tools/regen_state.py (MODULES) and tools/progress_gen.py (PLANNED) "
          "in the same commit; an unregistered module does not show up as untested, it does not show up at all."))
    sec("S04", "Environment, stack and history", "HANDOFF §4 and §6 (verbatim)",
        J(L(HANDOFF, 25, 25), L(HANDOFF, 36, 36)))
    sec("S05", "Architecture and data flow", "HANDOFF §5 (verbatim)", L(HANDOFF, 28, 33))
    sec("S06", "Module map (selected backend modules)", "brain/architecture.md Module Map (snapshot e803a99), trimmed",
        compact(J(L(MEM / "brain/architecture.md", 76, 86), L(MEM / "brain/architecture.md", 125, 139))))
    sec("S07", "The five generators (the entire catalogue)",
        "generators/*.py VERSION/FUNCTION constants; HANDOFF §5; brain/decisions.md 2026-09-21..24; current_phase.md",
        """| Generator | VERSION | Phase 1 template | FUNCTION | Boards | What it predicts and notable facts |
|---|---|---|---|---|---|
| rc_lowpass | 0.2.3 | TPL_004 | low_pass_filter | no MCU | Cutoff f_c over the tolerance box (π bracketed, G1); AC sweep in ngspice. 0.2.0 added pinned R1/C1 (`constraints.pinned`); 0.2.2 refuses a declared source that moves f_c past tolerance; 0.2.3 first swamps a large declared source with a larger R1 (smaller C) before refusing (decided with TypeSafe 2026-09-23). |
| voltage_divider | 0.1.0 | TPL_005 | voltage_divider | no MCU | vout_v (monotone corners), output impedance, bleed current, resistor dissipation. Its dissipation is decided exactly by its signed Stage 4 proof. |
| led_indicator | 0.2.0 | TPL_003 | led_indicator | arduino_uno, esp32_devkitc, blackpill_f411ce | led_current_ma from the Shockley diode and a Thevenin GPIO pin; GPIO current against the 20 mA recommended / 40 mA absolute limit; exact R1 dissipation since Task 4.5 (led_indicator 0.1.2, then 0.2.0 at Stage 5). |
| dht22_node | 0.2.0 | TPL_001 | temperature_humidity_sensor | arduino_uno, esp32_devkitc, blackpill_f411ce | Pull-up sink current with the line held low, idle data-line level, rail current (under mcu_as_100R, D2); pull-up vs cable rise time. DHT22 rise-time and sink limits are stated assumptions (Aosong publishes neither). |
| rs485_node | 0.2.0 | TPL_002 | modbus_rtu_master | arduino_uno, esp32_devkitc, blackpill_f411ce | Idle differential bus voltage v_ab against the ±200 mV receiver threshold (fail-safe bias), total bus load against the 54 Ω a driver is specified into. Terminator must be 1206: 5 V across 120 Ω is 208 mW, over three times an 0402's 62.5 mW. MAX3485 on a 3.3 V board. Thin M1 margin: a 5% terminator fault moves idle V_AB by 2.3% against the 2% gate (1.16× the gate on the Uno, 1.13× on 3.3 V boards). The Uno firmware drives the transceiver with SoftwareSerial on D10/D11. |

Generator protocol (generators/protocol.py): name, version, envelope() (accept or refuse by name), generate(), predict() (Interval bands), grid(), dependency_closure(). Registered generators must also implement claims() and may declare properties(intent). Free-form generation is out of scope: a request outside every envelope is refused, and the refusals are the backlog.

The MCU is represented in SPICE by a resistor sized from its run current: 100 Ω on the Uno (mcu_as_100R), 41 Ω for the ESP32-WROOM-32E, 132 Ω for the STM32F411. The DE/RE default pin of rs485_node is D2 on the Uno, GPIO4 on the ESP32-DevKitC and PB0 on the Black Pill.""")
    sec("S08", "IntentIR, patches and retries (X2, X4, X5)",
        "backend/core/intent_ir.py docstring; brain/decisions.md [2026-09-21] X5 accepted; [2026-09-21] X2 + X4 accepted",
        J(L(P2 / "backend/core/intent_ir.py", 2, 10),
          "SCHEMA_VERSION = \"2.2.0\" — 2.1.0 (Stage 2) added `revision`; 2.2.0 (Stage 4) added "
          "`SignOff.properties_hash`; older dumps still load.",
          "From [2026-09-21] X5 accepted:\n" + L(DM, 674, 677) + "\n" + L(DM, 700, 708),
          "From [2026-09-21] X2 + X4 accepted:\n" + L(DM, 762, 766), L(DM, 801, 809),
          L(DM, 821, 826), L(DM, 828, 839), L(DM, 844, 846), L(DM, 874, 879)))
    sec("S09", "Claims, verdicts and grades G0–G7", "backend/validation/claims.py (docstring and tables, verbatim)",
        J(L(P2 / "backend/validation/claims.py", 4, 26),
          "```python\n" + compact(J(L(P2 / "backend/validation/claims.py", 58, 80),
                                    L(P2 / "backend/validation/claims.py", 109, 112))) +
          "\nclass Verdict(str, Enum): holds, holds_defeasible, fails, not_applicable, not_assessed, out_of_scope\n```"))
    sec("S10", "The defeater register D1–D9", "backend/validation/defeaters.py (REGISTER rendered verbatim); HANDOFF §5",
        J(L(P2 / "backend/validation/defeaters.py", 4, 7), load_register(),
          "Status per the owner's handoff (§5, after the snapshot): D1 open (bench sheet docs/BENCH_D1.md; evidence-record "
          "code not built). D2 open, derived per claim since commit 94b61c1. D3 = criterion 12, deferred with trigger. D4 "
          "open. D5 open per design; closed by user sign-off. D6 n/a. D7 open (provenance records + verify tool built, "
          "uncommitted). D8 eliminated. D9 open per generator until under the M1 matrix."), core=True)
    # ------------------------------------------------------------------ middle
    sec("S11", "Proofs (Stage 4): properties proved from the netlist, signed, frozen",
        "brain/decisions.md [2026-09-23] Stage 4; plan/current_phase.md Stage 4 gates and not-done",
        J(L(DM, 1235, 1244), L(DM, 1266, 1279), compact(demote(L(CP, 588, 600), 1))))
    sec("S12", "Multi-MCU firmware (Stage 5)",
        "brain/decisions.md [2026-09-23] Stage 5; plan/current_phase.md Stage 5 gates and not-done",
        J(L(DM, 1534, 1537), L(DM, 1544, 1547), L(DM, 1564, 1570),
          compact(demote(L(CP, 722, 727), 1)), L(CP, 742, 745)))
    sec("S13", "Stage 6 (BOM + substitution) and D7 provenance — uncommitted work in progress",
        "HANDOFF §8 (verbatim); plan/current_phase.md 'Next — Stage 6'; facts as stated in the first live run's request files",
        J(L(HANDOFF, 47, 48), "Stage 6 plan text (current_phase.md):\n" + L(CP, 753, 758),
          "Also stated in the first live run's request files (tools/jev/requests/stage6_finish.json, "
          "pin_support_version_policy.json, x7_live_pricing.json), citing the owner's handoff: the suite on the working "
          "tree is 2123 passed, 30 skipped, 0 failed, with the uncommitted work green but unregistered; all 49 CI grid "
          "designs are byte-identical before and after the parts refactor; Stage 6 changed all five generators to honour "
          "constraints.pinned.<id> and left their VERSION strings unchanged; static exact-match prices carry "
          "price_asof 2026-07-25."), core=True)
    sec("S14", "Phase 1 — the twelve criteria and what v0.1.0 does not certify",
        "PHASE1_COMPLETE.md §2, §3, §5 (verbatim, trimmed)",
        J(L(P2 / "PHASE1_COMPLETE.md", 35, 48), L(P2 / "PHASE1_COMPLETE.md", 60, 70), L(P2 / "PHASE1_COMPLETE.md", 80, 88),
          ))
    sec("S15", "Phase 2 — stages, gates, and what each stage left not done",
        "HANDOFF §6; plan/current_phase.md (Stage 0–5 gates, verification tables)",
        J("Stage history (HANDOFF §6): " + L(HANDOFF, 37, 37),
          "Stage 0 grid gate (Task 0.4): control rc_lowpass@0.1.0: 7/7 points within 2%, worst 0.0000%; seeded fault P5 "
          "detected at 7/7 points outside 2%, worst 4.8403%. Stage 0 log gate: every request produces a complete log "
          "row (G1, schema-enforced).",
          compact(demote(L(CP, 414, 422), 1)), L(CP, 429, 432), compact(demote(L(CP, 519, 527), 1)),
          L(CP, 731, 733)))
    sec("S16", "Phase 2 deliverables: the canonical list versus what was built",
        "PRODUCT_MASTER.md Part 6 Phase 2; ROADMAP.md §5; brain/decisions.md [2026-08-22]; HANDOFF note",
        J(demote(L(P2 / "PRODUCT_MASTER.md", 332, 344), 1), "ROADMAP.md §5: " + L(P2 / "ROADMAP.md", 132, 135),
          L(P2 / "ROADMAP.md", 164, 167), L(P2 / "ROADMAP.md", 176, 179),
          "What was built instead is Stages 0–6 of PHASE_2_PLAN_v2.md (S15). PHASE_2_PLAN_v2.md, EVIDENCE_CLASSES.md and "
          "ARCHITECTURE_ASSURANCE_CASE.md are not in the repository. Precedence (set 2026-09-20): PHASE_2_PLAN_v2.md > "
          "PRODUCT_MASTER.md > EVIDENCE_CLASSES.md / ARCHITECTURE_ASSURANCE_CASE.md. No written Phase 2 exit gate exists "
          "in the repository."))
    sec("S17", "Phase 3 and later — the canonical roadmap",
        "PRODUCT_MASTER.md Part 3 Tier 3, Part 6 Phases 3–5, Part 7 External APIs, Part 9 pricing (verbatim, trimmed)",
        J(demote(L(P2 / "PRODUCT_MASTER.md", 174, 182), 1), demote(L(P2 / "PRODUCT_MASTER.md", 346, 373), 1),
          L(P2 / "PRODUCT_MASTER.md", 482, 484)))
    sec("S18", "PCB and CAD strategy (PCB_STRATEGY.md), including §9 'How this could be wrong'",
        "PCB_STRATEGY.md §3, §4, §5, §7, §8, §9, §10 (verbatim, trimmed)",
        J(L(P2 / "PCB_STRATEGY.md", 108, 122), "Audience sequence chosen: hobbyist -> PCB designer -> HVAC/controls. " +
          L(P2 / "PCB_STRATEGY.md", 136, 142),
          compact(L(P2 / "PCB_STRATEGY.md", 170, 177)),
          "**Step 2 is the one to build, and it is uniquely yours.** It is your explanation layer applied to geometry.",
          demote(L(P2 / "PCB_STRATEGY.md", 249, 263), 1),
          demote(L(P2 / "PCB_STRATEGY.md", 280, 306), 1), L(P2 / "PCB_STRATEGY.md", 310, 312)))
    sec("S19", "Competitive position and product claims",
        "brain/vision.md; MENTAL_MODEL.md §9 (verbatim, trimmed)",
        compact(demote(L(P2 / "MENTAL_MODEL.md", 242, 267), 1)))
    sec("S20", "Open issues", "HANDOFF §9 (verbatim); plan/current_phase.md; brain/timeline.md",
        J(L(HANDOFF, 51, 51),
          "Flaky test (timeline.md 2026-08-23): " + L(MEM / "brain/timeline.md", 90, 90).replace("**2026-08-23** — ", ""),
          L(CP, 463, 464)), core=True)
    # ------------------------------------------------------------------ end
    sec("S21", "Decisions the owner holds, and other open decisions (facts and options only)",
        "HANDOFF §7 (verbatim); tools/jev/requests/*.json states; PRODUCT_MASTER.md; PCB_STRATEGY.md; earlier report findings",
        J("Handoff §7 — decisions the user still owns (verbatim):\n" + L(HANDOFF, 40, 44),
          "#### D-1 RS-485 DE/RE pull-down\n" + facts_block("rs485_de_re_pulldown.json"),
          "#### D-2 Live pricing (X7)\n" + facts_block("x7_live_pricing.json"),
          "#### D-3 D1 bench session timing\n" + facts_block("d1_bench_timing.json"),
          "#### D-4 D7 datasheet verification pass: timing and order\n"
          "- Provenance is built but uncommitted: data/parts.py, data/figures.py (155 records, each with a kind — "
          "guaranteed, typical, derived, standard or stated assumption — a source, and the agent's reading written without "
          "opening the datasheet), scripts/verify_figures.py with an empty figure_verifications.json, and "
          "validation/figure_audit.py (perturb each figure; 145 pairs clean). Verification means a person opens each datasheet.\n"
          "- Order proposed in the earlier report: deterministic tiers first — figures that gate a critical claim; within "
          "a tier, stated_assumption and typical before guaranteed; then the smallest figure_audit margin. A judgment model "
          "would only break ties inside a tier.\n- Stage 6 substitution re-proves every property with the substitute "
          "part's figures before surfacing it.\n- The DHT22 rise-time and sink limits and the MAX485 DE/RE reset behaviour "
          "are stated assumptions.",
          "#### D-5 `kind` label on exact proofs\n" + facts_block("proof_kind_label.json"),
          "#### D-6 Explainer budget (max_tokens, cost, latency)\n" + facts_block("explainer_budget.json"),
          "#### D-7 Generator VERSION bumps after the Stage 6 pin-support change\n" + facts_block(
              "pin_support_version_policy.json",
              ["The deterministic byte-compare over the uncommitted Stage 6 code (grid points, Phase 1 examples, accepted "
               "corpus) and the envelope accept/refuse diff on the refusal corpus have not been run."]),
          "#### D-8 Stage 6 finishing versus Phase 3 start; the deferred 5%-of-engineer KPI\n" + facts_block("stage6_finish.json"),
          "#### D-9 The flaky accuracy test\n" + facts_block("accuracy_flake_policy.json"),
          "#### D-10 Phase 3 programme order\n"
          "- Phase 3 splits into three programmes: (A) the constraint layer + freerouting integration, which needs no "
          "customers; (B) industrial generators (DCV, kitchen hood, refrigeration, RS-485 industrial I/O with "
          "optoisolation); (C) enterprise features (private libraries, audit trail), which PCB_STRATEGY §9.3 gates on "
          "asking three HVAC controls people.\n- The first-listed Phase 3 class (DCV) needs a 24VAC-to-3.3V switching "
          "supply; switching converters and transient simulation are out of Phase 2 scope.\n- One engineer; Phase 3 is "
          "planned at months 8–18.",
          "#### D-11 The Gerber / Phase 3 KPI contradiction\n"
          "- Phase 3 KPI: 'One customer prompt-to-ordered-PCB within one business day.'\n- Gerber export + JLCPCB/PCBWay "
          "API integration and the DFM report are Phase 4 deliverables.\n- Part 7 lists 'JLCPCB API (Phase 3+)'.\n- The "
          "Pro pricing tier text says 'Gerber export (Phase 2+)'.\n- PCB_STRATEGY §7 lists Gerber export and fab APIs "
          "'right now' as a non-goal.",
          "#### D-12 Which Phase 2 deliverable list governs Phase 2 exit\n"
          "- PRODUCT_MASTER's Phase 2 list (free-form generation to 15 templates, ESP32/STM32, live BOM pricing, version "
          "history UI, Qdrant RAG on 500 excerpts, waveform viewer, substitution engine) differs from what was built "
          "(Stages 0–6 of PHASE_2_PLAN_v2).\n- Precedence: PHASE_2_PLAN_v2 > PRODUCT_MASTER. PHASE_2_PLAN_v2 is not in "
          "the repository. No written Phase 2 exit gate exists in the repository.",
          "#### D-13 Standard family to flag for Phase 3 boards\n"
          "- PRODUCT_MASTER Phase 3 names 'UL 508A flagging and safety class enforcement'; the kitchen-hood class 'flags "
          "UL 508A requirements and life-safety design rules'.\n- The earlier report (finding 10): UL 60730-1 covers "
          "automatic electrical controls; UL 61010-1 / 61010-2-201 cover programmable controllers; UL 508A covers the "
          "industrial control panel. Applicability is a liability decision for a person; Circuit OS should flag "
          "candidate families, never assert compliance.",
          "#### D-14 Criterion-12 timing\n"
          "- Trigger (decisions.md 2026-08-25): before the first external user is shown a generated explanation — a "
          "public launch, a demo to a prospect, or onboarding anyone outside the repo.\n- Phase 3 KPI: first enterprise "
          "contract signed.\n- The review costs about ten minutes of one EE-literate person's time; the protocol asks "
          "for three reviewers.",
          "#### D-15 Storing raw prompt text (needed for a live transcription-fidelity check, R1)\n"
          "- Today request_log stores prompt_hash, not the prompt text.\n- R1 in shadow mode on live traffic needs the "
          "raw prompt; a seeded prompt->gold-IntentIR corpus does not.\n- The existing 0/200 corpus measures envelope(), "
          "not transcription.",
          "#### D-16 Commit convention\n"
          "- HANDOFF §3: 'Commits conventional; commit/push only when asked.'\n- AGENTS.md worker mode: `git commit -m "
          "\"session: <brief description>\"`.\n- Memory commits use `brain:`; the last 40 commits on phase2-stage0 mix "
          "`feat(phase2):` (8), `brain:` (7), `fix(...)`, `test(...)`, `memory:` and `regen`.\n- The /update-memory "
          "command hardcodes a Windows user path."), core=True)
    sec("S22", "Reasoning on record — closing Phase 1 (brain/decisions.md, verbatim, trimmed)",
        "brain/decisions.md [2026-08-22] criterion 12 moved; PRODUCT_MASTER canonical; [2026-08-25] criterion 12 deferred",
        J(L(DM, 311, 323), L(DM, 333, 341), L(DM, 345, 349), L(DM, 369, 374), L(DM, 429, 436), L(DM, 444, 452)))
    sec("S23", "Reasoning on record — predict() as per-request truth; explanation derivability",
        "brain/decisions.md [2026-09-20] (two entries, verbatim, trimmed)",
        J(L(DM, 469, 475), L(DM, 482, 489), L(DM, 506, 511), L(DM, 530, 531), L(DM, 538, 544), L(DM, 556, 568)))
    sec("S24", "Reasoning on record — the LLM -> CircuitIR path removed",
        "brain/decisions.md [2026-09-21] (verbatim, trimmed)", J(L(DM, 723, 737), L(DM, 751, 756)))
    sec("S25", "Reasoning on record — X6 + X8, the defeater namespace, `kind` and the library floor",
        "brain/decisions.md [2026-09-21] X6 + X8 (verbatim, trimmed)",
        J(L(DM, 1033, 1040), L(DM, 1056, 1069), L(DM, 1090, 1098), L(DM, 1100, 1110),
          L(DM, 1206, 1216)))
    sec("S26", "Reasoning on record — RC swamping and the LED bound (decided with TypeSafe); the unverified three",
        "brain/decisions.md [2026-09-23] (two entries, verbatim, trimmed)",
        J(L(DM, 1431, 1474), L(DM, 1477, 1477), L(DM, 1519, 1528)))
    sec("S27", "Criterion 12 review protocol and the D1 bench sheet",
        "CRITERION_12_REVIEW.md §0–§3; docs/BENCH_D1.md (verbatim, trimmed)",
        J(L(P2 / "CRITERION_12_REVIEW.md", 11, 20),
          L(P2 / "CRITERION_12_REVIEW.md", 58, 60), L(P2 / "docs/BENCH_D1.md", 1, 12), L(P2 / "docs/BENCH_D1.md", 31, 37)))
    sec("S28", "The earlier research report — headline and fifteen findings",
        "reports/Jev decisions for Circuit OS Phase 3.md (verbatim; findings table without its evidence column)",
        J(". ".join(L(REPORT, 3, 3).split(". ")[:4]) + ". " +
          "**Do not keep the current >0.9 / 0.5–0.9 / <0.5 protocol as written.**" +
          L(REPORT, 3, 3).split("protocol as written.**")[1].split("**No live Jev call")[0].rstrip(),
          drop_cols(L(REPORT, 21, 37), {2})))
    sec("S29", "The earlier research report — thirty-three proposed Jev uses",
        "reports/Jev decisions for Circuit OS Phase 3.md (verbatim; some table columns dropped)",
        J(L(REPORT, 41, 41).split(" Assurance-case practice")[0],
          "Owner and engineering decisions (O1–O10):\n" + drop_cols(L(REPORT, 47, 58), {1, 2}),
          "Runtime and assurance layer (R1–R11), shadow first:\n" + drop_cols(L(REPORT, 64, 76), {1, 2, 4}),
          "Phase 3 labels (P1–P8):\n" + drop_cols(L(REPORT, 86, 95), {1}),
          "Dev tooling (T1–T4):\n" + "Jev earns four advisory" + L(REPORT, 99, 99).split("Jev earns four advisory")[1]))
    sec("S30", "The first live Jev run (2026-09-25) on seven small decision states",
        "tools/jev/RESULTS_2026-09-25.md (verbatim)", L(RESULTS, 1, 30))
    sec("S31", "Domain facts and formulas", "brain/knowledge.md; PCB_STRATEGY.md §3 enums",
        J(L(MEM / "brain/knowledge.md", 206, 220),
          "SignalType values in ir_schema.py: power, ground, digital, analog, i2c_sda, i2c_scl, spi_mosi, spi_miso, "
          "spi_sck, spi_cs, uart_tx, uart_rx, rs485_a, rs485_b, pwm, one_wire. ApplicationClass: hobby_arduino, "
          "iot_node, industrial_io, hvac_control, modbus_rtu."))
    return SECTIONS


HEADER_FULL = """# Circuit OS — project dossier (full)

Built 2026-09-24 for a Jev consultation. Everything below is taken from the Circuit OS repository snapshot (branch
phase2-stage0 at commit e803a99), the owner's handoff of 2026-09-25 (which describes one later commit, 94b61c1, and
uncommitted Stage 6 / D7 work), the earlier research report on Jev, and the first live Jev results. Each section has a
stable ID in square brackets and names its sources. Text is verbatim where marked; credentials and personal contact
details are removed. Where the dossier does not state something, it is not known here."""

HEADER_CORE = """# Circuit OS — project dossier (core)

A shorter version of the full dossier: the sections most relevant to open decisions, copied verbatim with the same
stable IDs. Built 2026-09-24 from the Circuit OS repository snapshot (phase2-stage0 at e803a99) and the owner's
handoff of 2026-09-25. Where the dossier does not state something, it is not known here."""


def render(sections, header):
    idx = "Sections: " + "; ".join(f"[{s['id']}] {s['title']}" for s in sections) + "."
    parts = [header, idx]
    for s in sections:
        parts.append(f"## [{s['id']}] {s['title']}\n*Sources: {s['sources']}*\n\n{s['body']}")
    return "\n\n".join(parts) + "\n"


def main():
    secs = build()
    full = render(secs, HEADER_FULL)
    core = render([s for s in secs if s["core"]], HEADER_CORE)
    for name, text in (("circuit_os_dossier.md", full), ("circuit_os_dossier_core.md", core)):
        hits = [p.pattern for p in SECRET_PATTERNS if p.search(text)]
        if hits:
            raise SystemExit(f"{name}: secret-like pattern(s) still present: {hits}")
        (HERE / name).write_text(text, encoding="utf-8")
    (HERE / "dossier_sections.json").write_text(json.dumps(
        {"header_full": HEADER_FULL, "header_core": HEADER_CORE, "sections": secs}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    for name, text in (("full", full), ("core", core)):
        print(f"{name}: {len(text):,} chars, est {len(text) / 4.2:,.0f} tokens, sha256 "
              f"{hashlib.sha256(text.encode()).hexdigest()[:16]}")
    for s in secs:
        print(f"  {s['id']} {'C' if s['core'] else ' '} {len(s['body']):6,}  {s['title'][:70]}")


if __name__ == "__main__":
    main()
