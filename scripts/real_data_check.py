"""
Circuit OS against real published circuits.

    python scripts/real_data_check.py [--json out.json]

For every design in `backend/data/reference_designs.json` (real boards, standards and
vendor application notes, each with its source):

  1. measure the REAL circuit with ngspice — the physical figure its family is judged by;
  2. ask Circuit OS for the same job through the form (0 API calls) and measure what it
     generates the same way, from its own netlist;
  3. judge both against criteria taken from the standards and datasheets, not from the
     generators — and say plainly when Circuit OS refuses, and why.

ngspice is the oracle; nothing here reads a generator's `predict()` or its claims. The
generators supply only the design that is being judged.

Criteria (each names its source):
  voltage_divider  V_out within 2 % of the request (nominal) · worst case over 1 % parts reported
  led_indicator    LED current ≤ the LED's continuous rating · pin current ≤ 20 mA (ATmega328P
                   recommended; the 3.3 V boards' limits are lower still) · current within ±20 %
                   of the request
  rs485_node       worst-case idle V_AB ≥ 200 mV, the TIA/EIA-485 receiver threshold (TI SLLA272D §4),
                   over supply, tolerance and receiver loading · Modbus bias 450–650 Ω when polarized
  dht22_node       pull-up inside the datasheet's use · 10–90 % rise time and sink current reported
                   over cable length
  rc_lowpass       f_c within 5 % of the request (nominal); source loading reported
"""

from __future__ import annotations

import itertools
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
for _k, _v in {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "postgresql+asyncpg://x:x@localhost/x",
               "REDIS_URL": "redis://localhost:6379/0", "SECRET_KEY": "x" * 40}.items():
    os.environ.setdefault(_k, _v)

import ngspice_batch as ng  # noqa: E402

CORPUS = ROOT / "backend" / "data" / "reference_designs.json"
VT = 1.380649e-23 * 300.15 / 1.602176634e-19          # ngspice's 27 °C

# Where a figure below is a judgement, its source is named beside it.
RECEIVER_THRESHOLD_V = 0.200      # TIA/EIA-485, TI SLLA272D §4 "Signal Levels"
BIAS_NOISE_MARGIN_V = 0.050       # TI SLLA272D §7: V_AB = 200 mV + V_noise; 0.25 V used in the worked example
MODBUS_BIAS_OHM = (450.0, 650.0)  # Modbus over Serial Line V1.02 §3.4.6
PIN_LIMIT_MA = 20.0               # ATmega328P recommended per-pin current (datasheet; 40 mA is the absolute maximum)
RECEIVER_INPUT_OHM = 12_000.0     # one RS-485 unit load, TI SLLA272D §8
CABLE_PF_PER_M = (50.0, 100.0)    # unshielded twisted pair to flat three-core, typical
PIN_PF = 10.0                     # MCU pin plus DHT22 package, order of magnitude


# ── Normalised designs ───────────────────────────────────────────────────────

@dataclass
class Design:
    name: str
    elements: List[Tuple]                       # ("R", name, a, b, ohm) | ("C", …, farad) | ("V", …, volts) | ("VAC", …) | ("D", name, a, b, model)
    tol: Dict[str, float] = field(default_factory=dict)      # element → relative tolerance
    supply_srcs: Tuple[str, ...] = ()           # sources that follow the supply
    models: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    roles: Dict[str, str] = field(default_factory=dict)
    led: Optional[Dict[str, float]] = None      # n, vf_min, vf_typ, vf_max, if_ref_ma, if_max_ma


def led_is(vf: float, n: float, if_ref_a: float) -> float:
    return if_ref_a / math.expm1(vf / (n * VT))


def with_supply(d: Design, volts: float, resistors: Optional[Dict[str, float]] = None,
                diode: Optional[Tuple[str, float]] = None, extra: Tuple = ()) -> ng.Copy:
    els: List[Tuple] = []
    for e in d.elements:
        kind, name = e[0], e[1]
        if kind == "V" and name in d.supply_srcs:
            els.append(("V", name, e[2], e[3], volts))
        elif kind in ("R", "C") and resistors and name in resistors:
            els.append((kind, name, e[2], e[3], resistors[name]))
        else:
            els.append(e)
    models = dict(d.models)
    if diode:
        models[diode[0]] = (diode[1], d.led["n"] if d.led else 2.0)
    return ng.Copy(elements=els + list(extra), models=models)


def corners(d: Design, kinds: str = "R") -> List[Dict[str, float]]:
    """Every combination of each toleranced element at its low or high end."""
    names = [e[1] for e in d.elements if e[0] in kinds and d.tol.get(e[1], 0) > 0]
    base = {e[1]: e[4] for e in d.elements if e[0] in kinds}
    out = []
    for signs in itertools.product((-1, 1), repeat=len(names)):
        v = dict(base)
        for n, s in zip(names, signs):
            v[n] = base[n] * (1 + s * d.tol[n])
        out.append(v)
    return out or [dict(base)]


def from_corpus(entry: Dict[str, Any], variant: Optional[Dict[str, Any]] = None) -> Design:
    subs = variant or {}
    leds = CORP["leds"]
    els: List[Tuple] = []
    tol: Dict[str, float] = {}
    srcs: List[str] = []
    models: Dict[str, Tuple[float, float]] = {}
    led = None
    for e in entry["elements"]:
        ohm = e.get("ohm")
        if isinstance(ohm, str) and ohm.startswith("$"):
            ohm = subs[ohm[1:]]
        k = e["kind"]
        if k == "R":
            els.append(("R", e["id"], e["a"], e["b"], float(ohm)))
            tol[e["id"]] = e.get("tol", 0.0)
        elif k == "C":
            els.append(("C", e["id"], e["a"], e["b"], float(e["farad"])))
            tol[e["id"]] = e.get("tol", 0.0)
        elif k == "V":
            els.append(("VAC" if e.get("ac") else "V", e["id"], e["a"], e["b"],
                        1.0 if e.get("ac") else entry["supply_v"]["nominal"]))
            srcs.append(e["id"])
        elif k == "LED":
            led = leds[e["led"]]
            model = f"D_{e['led']}"
            models[model] = (led_is(led["vf_typ_v"], led["n"], led["if_ref_ma"] / 1000), led["n"])
            els.append(("D", e["id"], e["a"], e["b"], model))
    return Design(entry["id"], els, tol, tuple(srcs), models, led=led and {
        "n": led["n"], "vf_min": led["vf_min_v"], "vf_typ": led["vf_typ_v"], "vf_max": led["vf_max_v"],
        "if_ref_ma": led["if_ref_ma"], "if_max_ma": led["if_max_ma"]})


def from_generated(generator, intent, circuit, bench_lines: List[str] = ()) -> Design:
    from generators.netlist.spice import SpiceNetlistGenerator
    from proof.netlist import parse

    text = SpiceNetlistGenerator().generate(circuit)
    nl = parse(text).with_bench(list(bench_lines)) if bench_lines else parse(text)
    els: List[Tuple] = []
    tol: Dict[str, float] = {}
    srcs: List[str] = []
    for e in nl.elements:
        if e.kind == "R":
            els.append(("R", e.name, e.a, e.b, float(e.value)))
        elif e.kind == "C":
            els.append(("C", e.name, e.a, e.b, float(e.value)))
        elif e.kind == "V":
            if e.ac:
                els.append(("VAC", e.name, e.a, e.b, 1.0))
            else:
                els.append(("V", e.name, e.a, e.b, float(e.value)))
            srcs.append(e.name)
        elif e.kind == "D":
            els.append(("D", e.name, e.a, e.b, e.model))
    models = {m: (float(i), float(n)) for m, (i, n) in nl.diode_models.items()}
    by_id = {c.id: c for c in circuit.components}
    from proof.prover import capacitor_tolerance, resistor_tolerance
    for e in els:
        if e[0] in ("R", "C") and "_" in e[1]:
            comp = by_id.get(e[1].split("_", 1)[1])
            if comp is not None and comp.part_number:
                tol[e[1]] = float((resistor_tolerance if e[0] == "R" else capacitor_tolerance)(comp.part_number)[0])
    for e in els:                                  # the far-end terminator a generator's own bench line adds: a 1 % part too
        if e[0] == "R" and e[1].upper().startswith("R_FAR"):
            tol[e[1]] = 0.01
    led = None
    if models:
        led = dict(n=next(iter(models.values()))[1], vf_min=1.6, vf_typ=2.0, vf_max=2.4, if_ref_ma=20.0, if_max_ma=25.0)
    return Design("generated:" + generator.name, els, tol, tuple(srcs), models, led=led)


# ── Family metrics (all by ngspice) ──────────────────────────────────────────

def supply_sources(d: Design) -> Tuple[str, ...]:
    return d.supply_srcs


def m_divider(d: Design, supply: float, out: str, r_top: str, r_bot: str, target: float) -> Dict[str, Any]:
    cps = [with_supply(d, supply, resistors=c) for c in corners(d)]
    for c in cps:
        c.probes = [out]
    res = ng.run_op(cps)
    vals = [r[out] for r in res]
    nom = ng.run_op([ng.Copy(elements=with_supply(d, supply).elements, probes=[out])])[0][out]
    rt = {e[1]: e[4] for e in d.elements if e[0] == "R"}
    ra, rb = rt[r_top], rt[r_bot]
    return {
        "vout_v": nom, "vout_error_pct": 100 * (nom - target) / target,
        "vout_worst_low_v": min(vals), "vout_worst_high_v": max(vals),
        "worst_error_pct": 100 * max(abs(min(vals) - target), abs(max(vals) - target)) / target,
        "r_top_ohm": ra, "r_bottom_ohm": rb, "r_total_ohm": ra + rb,
        "bleed_current_ua": 1e6 * supply / (ra + rb), "output_impedance_ohm": ra * rb / (ra + rb),
        "pass": abs(nom - target) / target <= 0.02,
    }


def m_led(d: Design, supply: float, pin: str, anode: str, r_name: str, target_ma: Optional[float]) -> Dict[str, Any]:
    led = d.led
    model = next(iter(d.models))
    r_nom = {e[1]: e[4] for e in d.elements if e[0] == "R"}
    cases = []
    for vf in (led["vf_min"], led["vf_typ"], led["vf_max"]):
        for r_scale in (1 - d.tol.get(r_name, 0), 1.0, 1 + d.tol.get(r_name, 0)):
            for s in (supply * 0.95, supply, supply * 1.05):
                is_ = led_is(vf, led["n"], led["if_ref_ma"] / 1000)
                c = with_supply(d, s, resistors={r_name: r_nom[r_name] * r_scale}, diode=(model, is_))
                c.probes = [pin, anode]
                cases.append((vf, r_scale, s, c))
    res = ng.run_op([c for *_, c in cases])
    cur = []
    for (vf, r_scale, s, _), r in zip(cases, res):
        cur.append(1000 * (r[pin] - r[anode]) / (r_nom[r_name] * r_scale))
    nominal = [i for (vf, rs, s, _), i in zip(cases, cur)
               if vf == led["vf_typ"] and abs(rs - 1) < 1e-12 and s == supply][0]
    out = {"current_ma": nominal, "current_min_ma": min(cur), "current_max_ma": max(cur),
           "r_ohm": r_nom[r_name], "led_if_max_ma": led["if_max_ma"]}
    ok = max(cur) <= led["if_max_ma"] and max(cur) <= PIN_LIMIT_MA
    if target_ma:
        out["target_ma"] = target_ma
        out["error_pct"] = 100 * (nominal - target_ma) / target_ma
        ok = ok and abs(nominal - target_ma) / target_ma <= 0.20
    out["pass"] = bool(ok)
    return out


def m_rs485(d: Design, supply_range: Tuple[float, float, float], a: str, b: str, bias: Tuple[str, str] = ()) -> Dict[str, Any]:
    tie = [("R", "TIEA", a, "0", 1e9), ("R", "TIEB", b, "0", 1e9)]
    rx_cases = {"no receivers loading the pair": [],
                "2 receivers (12 kΩ from each line to ground each)": [("R", "RXA1", a, "0", RECEIVER_INPUT_OHM), ("R", "RXB1", b, "0", RECEIVER_INPUT_OHM),
                                                                     ("R", "RXA2", a, "0", RECEIVER_INPUT_OHM), ("R", "RXB2", b, "0", RECEIVER_INPUT_OHM)]}
    worst = {}
    for label, rx in rx_cases.items():
        cps = []
        for s in supply_range:
            for c in corners(d):
                cp = with_supply(d, s, resistors=c, extra=tuple(tie + rx))
                cp.diffs = [(a, b)]
                cps.append(cp)
        res = ng.run_op(cps)
        vals = [r[f"{a}-{b}"] for r in res]
        worst[label] = (min(vals), max(vals))
    nom_cp = with_supply(d, supply_range[1], extra=tuple(tie))
    nom_cp.diffs = [(a, b)]
    nominal = ng.run_op([nom_cp])[0][f"{a}-{b}"]
    lo = min(v[0] for v in worst.values())
    out = {"vab_nominal_v": nominal, "vab_worst_low_v": lo, "vab_by_loading_v": {k: [round(x, 4) for x in v] for k, v in worst.items()},
           "meets_threshold": lo >= RECEIVER_THRESHOLD_V, "margin_over_threshold_mv": 1000 * (lo - RECEIVER_THRESHOLD_V),
           "ti_margin_met": lo >= RECEIVER_THRESHOLD_V + BIAS_NOISE_MARGIN_V}
    if bias:
        rr = {e[1]: e[4] for e in d.elements if e[0] == "R"}
        out["bias_ohm"] = [rr[bias[0]], rr[bias[1]]]
        out["bias_in_modbus_window"] = all(MODBUS_BIAS_OHM[0] <= x <= MODBUS_BIAS_OHM[1] for x in out["bias_ohm"])
    out["pass"] = bool(out["meets_threshold"])
    return out


def m_dht(r1: float, supply: float, cable_m: float) -> Dict[str, Any]:
    rows = {}
    for pf in CABLE_PF_PER_M:
        c = cable_m * pf * 1e-12 + PIN_PF * 1e-12
        rows[f"{pf:g} pF/m"] = {"rise_us": 1e6 * ng.run_tran_rise(r1, c, supply)}
    return {"r1_ohm": r1, "cable_m": cable_m, "sink_current_ma": 1000 * supply / r1, "rise_10_90": rows}


def m_rc(d: Design, out: str, in_node: str, r_name: str, c_name: str, target_hz: Optional[float], src_ohm: float = 50.0) -> Dict[str, Any]:
    r = {e[1]: e[4] for e in d.elements if e[0] == "R"}[r_name]
    c = {e[1]: e[4] for e in d.elements if e[0] == "C"}[c_name]
    ac = [e for e in d.elements if e[0] == "VAC"][0]

    def fc(rs: float, cs: float, extra_r: float = 0.0) -> float:
        els = [("VAC", ac[1], "src", "0", 1.0)]
        els += [("R", "RS", "src", in_node, max(extra_r, 1e-3)),
                ("R", r_name, in_node, out, rs), ("C", c_name, out, "0", cs)]
        return ng.run_ac_cutoff(els, out, f_lo=0.5, f_hi=5e6)

    nom = fc(r, c)
    cs = [fc(r * (1 + sr * d.tol.get(r_name, 0)), c * (1 + sc * d.tol.get(c_name, 0))) for sr in (-1, 1) for sc in (-1, 1)]
    loaded = fc(r, c, extra_r=src_ohm)
    o = {"r_ohm": r, "c_farad": c, "fc_hz": nom, "fc_low_hz": min(cs), "fc_high_hz": max(cs),
         "fc_shift_with_%gohm_source_pct" % src_ohm: 100 * (loaded - nom) / nom}
    if target_hz:
        o["target_hz"] = target_hz
        o["error_pct"] = 100 * (nom - target_hz) / target_hz
        o["pass"] = abs(nom - target_hz) / target_hz <= 0.05
    else:
        o["pass"] = True
    return o


# ── Asking Circuit OS ────────────────────────────────────────────────────────

def ask_circuit_os(request: Dict[str, Any]):
    from ai.form_producer import FormProducer
    from generators.registry import default_registry

    reg = default_registry()
    intent = FormProducer(reg).build(request["function"], dict(request["fields"]))
    dispatch = reg.dispatch(intent)
    if not dispatch.accepted:
        return None, None, None, dispatch.refusal_summary()
    gen = dispatch.generator
    circuit = gen.generate(intent)
    return gen, intent, circuit, None


def bench_lines(gen, intent, prop_id: str) -> List[str]:
    for p in gen.properties(intent):
        if p.id == prop_id:
            return [b.line for b in p.bench]
    return []


# ── The check ────────────────────────────────────────────────────────────────

def run() -> Dict[str, Any]:
    global CORP
    CORP = json.loads(CORPUS.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []
    for entry in CORP["designs"]:
        fam = entry["family"]
        variants = [dict(zip(entry["variants"].keys(), vals)) for vals in zip(*entry["variants"].values())] if entry.get("variants") else [None]
        for var in variants:
            row: Dict[str, Any] = {"id": entry["id"] + (f"[{list(var.values())[0]}]" if var else ""), "family": fam,
                                   "title": entry["title"], "evidence": entry["source"]["evidence"], "request": entry["request"]}
            ref = from_corpus(entry, var)
            s = entry["supply_v"]
            req = json.loads(json.dumps(entry["request"]))
            fields = req["fields"]

            if fam == "voltage_divider":
                target = fields["vout_v"]
                row["real"] = m_divider(ref, s["nominal"] if fields["supply_v"] == s["nominal"] else fields["supply_v"], "out",
                                        "R1" if "R1" in {e[1] for e in ref.elements} else "R3",
                                        "R2" if "R2" in {e[1] for e in ref.elements} else "R6", target)
                gen, intent, circuit, why = ask_circuit_os(req)
                if gen is None:
                    row["generated"] = {"refused": why}
                else:
                    g = from_generated(gen, intent, circuit)
                    row["generated"] = m_divider(g, fields["supply_v"], "vout", "R_R1", "R_R2", target)
                    row["generated"]["parts"] = [(c.id, c.part_number) for c in circuit.components]

            elif fam == "led_indicator":
                sup = fields["supply_v"]
                real = m_led(ref, sup, "pin", "anode", [e[1] for e in ref.elements if e[0] == "R" and e[1] != "RP"][0], None)
                row["real"] = real
                fields["led_current_ma"] = round(real["current_ma"], 2)
                req["fields"] = fields
                row["request"] = req
                gen, intent, circuit, why = ask_circuit_os(req)
                if gen is None:
                    row["generated"] = {"refused": why}
                else:
                    g = from_generated(gen, intent, circuit)
                    row["generated"] = m_led(g, sup, "led_ctrl", "led_anode", "R_R1", fields["led_current_ma"])
                    # the real design, judged against the same target the request names
                    row["real"] = m_led(ref, sup, "pin", "anode", [e[1] for e in ref.elements if e[0] == "R" and e[1] != "RP"][0],
                                        fields["led_current_ma"])

            elif fam == "rs485_node":
                sr = (s["min"], s["nominal"], s["max"])
                bias = ("RB1", "RB2") if {"RB1", "RB2"} <= {e[1] for e in ref.elements} else ()
                row["real"] = m_rs485(ref, sr, "a", "b", bias)
                gen, intent, circuit, why = ask_circuit_os(req)
                if gen is None:
                    row["generated"] = {"refused": why}
                else:
                    g = from_generated(gen, intent, circuit, bench_lines(gen, intent, "rs485.failsafe_bias"))
                    sup = fields["supply_v"]
                    row["generated"] = m_rs485(g, (sup * 0.95, sup, sup * 1.05), "rs485_a", "rs485_b", ("R_R2", "R_R3"))
                    row["generated"]["parts"] = [(c.id, c.part_number) for c in circuit.components]

            elif fam == "dht22_node":
                r1 = [e[4] for e in ref.elements if e[1] == "R1"][0]
                sup = fields["supply_v"]
                row["real"] = {f"{m:g} m": m_dht(r1, sup, m) for m in (0.3, 1.0, 3.0, 10.0)}
                row["generated"] = {}
                for m in (0.3, 1.0, 3.0, 10.0):
                    rq = json.loads(json.dumps(req))
                    rq["fields"]["cable_length_m"] = m
                    gen, intent, circuit, why = ask_circuit_os(rq)
                    if gen is None:
                        row["generated"][f"{m:g} m"] = {"refused": why}
                    else:
                        r1g = [c for c in circuit.components if c.id == "R1"][0]
                        from generators.netlist.spice import _parse_ohms
                        ohm = float(_parse_ohms(str(r1g.value)))
                        row["generated"][f"{m:g} m"] = dict(m_dht(ohm, sup, m), part=r1g.part_number)

            elif fam == "rc_lowpass":
                gen_target = fields["cutoff_hz"]
                row["real"] = m_rc(ref, "out", "in", "R", "C", gen_target)
                gen, intent, circuit, why = ask_circuit_os(req)
                if gen is None:
                    row["generated"] = {"refused": why}
                else:
                    g = from_generated(gen, intent, circuit)
                    row["generated"] = m_rc(g, "out", "in", "R_R1", "C_C1", gen_target)
                    row["generated"]["parts"] = [(c.id, c.part_number, c.value) for c in circuit.components]
            results.append(row)
    return {"results": results}


def _fmt(x: Any) -> str:
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)


def render(out: Dict[str, Any]) -> str:
    lines = []
    for r in out["results"]:
        lines.append(f"\n=== {r['id']}  [{r['family']}; evidence: {r['evidence']}]")
        lines.append(f"    {r['title']}")
        lines.append(f"    asked of Circuit OS: {json.dumps(r['request']['fields'])}")
        for who in ("real", "generated"):
            v = r.get(who)
            if v is None:
                continue
            if r["family"] == "dht22_node":
                for cab, m in v.items():
                    if "refused" in m:
                        lines.append(f"    {who:9s} {cab:>7s}: REFUSED — {m['refused']}")
                    else:
                        rise = ", ".join(f"{k}: {x['rise_us']:.2f} µs" for k, x in m["rise_10_90"].items())
                        lines.append(f"    {who:9s} {cab:>7s}: R1={m['r1_ohm']:g} Ω  sink={m['sink_current_ma']:.2f} mA  rise(10–90) {rise}")
                continue
            if "refused" in v:
                lines.append(f"    {who:9s}: REFUSED — {v['refused']}")
                continue
            body = {k: _fmt(x) for k, x in v.items() if k not in ("parts",)}
            lines.append(f"    {who:9s}: " + "  ".join(f"{k}={x}" for k, x in body.items()))
            if v.get("parts"):
                lines.append(f"              parts: {v['parts']}")
    return "\n".join(lines)


if __name__ == "__main__":
    out = run()
    print(render(out))
    if "--json" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--json") + 1])
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        print("\nwrote", path)
