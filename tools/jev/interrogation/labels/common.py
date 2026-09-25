"""Shared helpers for the Phase 3 / assurance-layer labelling interrogation of Jev.

Every labelled set is built by a generator script in this directory, written to
`sets/<set_id>.json`, and hashed (sha256 over the file bytes) *before* any Jev call.
Labels come from construction, published standard text, code or computation —
never from Jev. See `prereg.json` for the frozen hashes.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import random
from typing import Any, Dict, List

HERE = pathlib.Path(__file__).resolve().parent
SETS = HERE / "sets"

#: Code snapshot the D7/D9/R7 generators read (read-only). origin/phase2-stage0 at e803a99
#: per the owner's handoff; it lacks the uncommitted §8 D7/Stage 6 files.
SNAPSHOT = pathlib.Path(os.environ.get(
    "CIRCUIT_OS_SNAPSHOT",
    "/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/p2"))

PINNED_MODEL = "jev-1.13.0"
SEED = 20260925

#: Citations shared by several sets. Each quote was read from the source during this session.
CITATIONS: Dict[str, Dict[str, str]] = {
    "TI_SLLA353": {
        "title": "Texas Instruments, Isolation Glossary (SLLA353A, rev. Sep 2017)",
        "url": "https://www.ti.com/lit/an/slla353/slla353.pdf",
        "quote": ("Pollution Degree 1 — No pollution or only dry, nonconductive pollution occurs. The pollution has "
                  "no influence. Pollution Degree 2 — Only nonconductive pollution occurs. However, a temporary "
                  "conductivity caused by condensation is to be expected. Pollution Degree 3 — Conductive pollution "
                  "occurs or dry non-conductive pollution occurs which becomes conductive due to condensation which "
                  "is to be expected. Pollution Degree 4 – Continuous conductivity occurs due to conductive dust, "
                  "rain, or other wet conditions. ... Overvoltage Categories ... four different levels as indicated "
                  "in IEC 60664. I: Signal level — Special protected equipment or parts of equipment, for example, "
                  "circuit board inside a DVD player. II: Local level — Portable equipment that is supplied from the "
                  "wall outlet ... III: Distribution level — Equipment in fixed installation such as HVAC system ... "
                  "IV: Primary supply level — Equipment for use at the origin of the installations such as overhead "
                  "lines, cable systems"),
    },
    "TI_SLUP419": {
        "title": "Texas Instruments, Demystifying Clearance and Creepage Distance for High-Voltage End Equipment (SLUP419, Mar 2024)",
        "url": "https://www.ti.com/lit/pdf/slup419",
        "quote": ("Pollution degree 1: ... These systems are sealed to exclude dust and moisture, or the PCB uses "
                  "conformal coating ... Pollution degree 2: ... labs, offices and enclosures for servers, "
                  "telecommunications equipment ... Pollution degree 3: ... industrial applications, farming equipment "
                  "and unheated factory rooms. Pollution degree 4: ... common for outdoor applications. ... Category I: "
                  "... circuits connected in a way that takes measures to limit overvoltage transients. Examples include "
                  "equipment such as 24-VAC thermostats and sprinkler systems connected to the mains through a step-down "
                  "transformer. Category II: ... equipment supplied from a fixed installation. Examples include equipment "
                  "plugged into an outlet ... Category III: ... equipment with a fixed installation subject to special "
                  "requirements. Examples include equipment permanently connected such as switches within a fuse panel, "
                  "air conditioners or industrial machinery hardwired to the AC mains. Category IV: ... equipment used at "
                  "the origin of installation ... Examples include electricity meters"),
    },
    "TI_SLLA070": {
        "title": "Texas Instruments, RS-422 and RS-485 Standards Overview and System Configurations (SLLA070D, rev. May 2010)",
        "url": "https://www.ti.com/lit/pdf/slla070",
        "quote": ("RS-485-compliant drivers and receivers are specified for operation with a common-mode range of -7 V "
                  "to 12 V. ... when the ground potential between the remote grounds is stretched to its maximum limit "
                  "of ±7 V. If driver 2 is connected to the ground that is 7 V lower than the ground for driver 1, a "
                  "potential close to +12 V can exist on the output of driver 2 (assuming VCC = 5 V). ... The approach "
                  "to tolerate ground potential differences up to several kilovolts across a robust RS-485 data link "
                  "and over long distance is the galvanic isolation"),
    },
    "TI_SLLA370": {
        "title": "Texas Instruments, How To Simplify Isolated 24V PLC Digital Input Module Designs (SLLA370D, rev. Jun 2025)",
        "url": "https://www.ti.com/lit/pdf/slla370",
        "quote": ("Digital Input (DI) modules are used in Programmable Logic Controllers (PLCs) and Motor Drives to "
                  "receive 24V digital inputs from field sensors and switches. Isolation is used to manage ground "
                  "potential differences."),
    },
    "ULSE_508A": {
        "title": "UL Standards & Engagement, UL 508A Industrial Control Panels — Scope",
        "url": "https://www.shopulstandards.com/ProductDetail.aspx?productId=UL508A",
        "quote": ("1.1 These requirements cover industrial control panels intended for general industrial use, operating "
                  "from a voltage of 1000 volts or less. ... 1.2 ... industrial control panels primarily intended for "
                  "flame safety supervision of combustible fuel type equipment ... 1.3 This equipment consists of "
                  "assemblies of two or more power circuit components ... or control circuit components ... mounted on, "
                  "or contained within, an enclosure, or are mounted on a sub-panel. ... 1.11 Assemblies of electrical "
                  "control units ... for fire-protective signaling systems are covered by ... UL 864. ... 1.13 Equipment "
                  "intended to supply automatic illumination, power, or both, to critical areas and equipment essential "
                  "to safety of human life is covered by ... UL 924."),
    },
    "DLS_60730": {
        "title": "D.L.S. Electronic Systems, EN IEC 60730-1 Automatic electrical controls — scope summary",
        "url": "https://www.dlsemc.com/iec-en-60730-1-automatic-electrical-controls-part-1-general-requirements/",
        "quote": ("EN IEC 60730-1 applies to automatic electrical controls for use in, on, or in association with "
                  "equipment for household and similar use. The equipment may use electricity, gas, oil, solid fuel ... "
                  "This standard is applicable to controls for building automation within the scope of ISO 16484. ... "
                  "also applies to automatic electrical controls for equipment that may be used by the public, such as "
                  "equipment intended to be used in shops, offices, hospitals, farms and commercial and industrial "
                  "applications. An example would be controls for commercial catering, heating and air-conditioning "
                  "equipment."),
    },
    "PANASONIC_61010_2_201": {
        "title": "Panasonic Industrial Devices, Implementation of the New IEC 61010-2-201 Standard For The PLC Market (May 2016)",
        "url": "https://na.industrial.panasonic.com/blog/implementation-new-iec-61010-2-201-standard-plc-market",
        "quote": ("IEC 61010-2-201 is a specific standard under IEC 61010 that specifically addresses safety requirements "
                  "and related verification tests for PLCs as well as a variety of other types of industrial control "
                  "equipment. The control equipment covered under the scope of this standard include: Programmable "
                  "controllers (PLCs and programmable automation controllers, PACs) ... Industrial computers, as well as "
                  "programming and debugging tools (PADTs) ... Human-machine interfaces (HMIs)"),
    },
    "UL_61010_2_201_SEARCH": {
        "title": "UL Solutions whitepaper 'Programmable Logic Controllers and IEC 61010-2-201' (via search summary; direct fetch blocked)",
        "url": "https://code-authorities.ul.com/wp-content/uploads/sites/40/2015/09/IEC-61010-2-201_2005_V1.pdf",
        "quote": ("control equipment ... include programmable controllers (PLCs and PACs), components of distributed "
                  "control systems (DCSs), components of remote input/output (I/O) systems, industrial computers ... "
                  "HMIs ... These products have as their intended use the command and control of machines, automated "
                  "manufacturing and industrial processes."),
    },
    "PRODUCT_MASTER": {
        "title": "Circuit OS PRODUCT_MASTER.md (snapshot e803a99), Tier 3 and Phase 3",
        "url": "file:p2/PRODUCT_MASTER.md:174-190,346-359",
        "quote": ("Commercial Kitchen Hood Controllers: ... dry contact inputs from Ansul fire suppression system, relay "
                  "outputs for gas valve shutoff and equipment lockout ... The system flags UL 508A requirements and "
                  "life-safety design rules."),
    },
    "TEMPLATE_B14": {
        "title": "tools/jev/templates/phase3_labels.questions.json (B14 draft questions)",
        "url": "file:tools/jev/templates/phase3_labels.questions.json",
        "quote": "net_role / env_label / isolation_needed / standard_family_flag / possibly_life_safety definitions",
    },
    "TEMPLATE_B13": {
        "title": "tools/jev/templates/refusal_backlog.questions.json (B13 draft question)",
        "url": "file:tools/jev/templates/refusal_backlog.questions.json",
        "quote": "refusal_label criteria",
    },
    "TEMPLATE_B4": {
        "title": "tools/jev/templates/d7_verification_order.questions.json (B4 draft question)",
        "url": "file:tools/jev/templates/d7_verification_order.questions.json",
        "quote": "vv_<figure_id> score rubric",
    },
    "WIKI_CURRENT_LOOP": {
        "title": "Wikipedia, Current loop",
        "url": "https://en.wikipedia.org/wiki/Current_loop",
        "quote": "Many instrumentation manufacturers produce 4–20 mA sensors which are \"loop powered\".",
    },
    "JEV_JAGGEDNESS": {
        "title": "TypeSafe docs, Jev 1.13 jaggedness (reviewed 2026-09-17)",
        "url": "https://docs.typesafe.ai/model-jaggedness/jev-1.13.md",
        "quote": "It struggles with tasks that require numeric precision. ... Jev is not a calculator.",
    },
}


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pick_subset(ids: List[str], k: int, salt: str) -> List[str]:
    """Deterministic, pre-registered subset (seeded by SEED and the set name)."""
    rng = random.Random(f"{SEED}:{salt}")
    ids = sorted(ids)
    return sorted(rng.sample(ids, min(k, len(ids))))


def write_set(set_id: str, payload: Dict[str, Any]) -> pathlib.Path:
    SETS.mkdir(exist_ok=True)
    payload = dict(payload)
    payload.setdefault("set_id", set_id)
    payload.setdefault("created_utc", datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    payload.setdefault("pinned_model", PINNED_MODEL)
    path = SETS / f"{set_id}.json"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {path.name}: {len(payload.get('items', []))} items, sha256 {file_sha(path)}")
    return path


def cite(*ids: str) -> List[Dict[str, str]]:
    return [{"id": i, **CITATIONS[i]} for i in ids]
