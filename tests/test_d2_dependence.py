"""
D2 derived per claim — `brain/decisions.md` [2026-09-24] D1, D2, D7.

A claim cites D2 only where the real microcontroller can reach it:

1. its quantity depends on an MCU model element — decided by symbolic nodal
   analysis (`proof/dependence.py`) and checked here **against ngspice**, by
   perturbing the supply resistor and the pin model separately and watching
   what moves;
2. it measures a node an MCU pin sits on that the netlist does not model
   (`mcu_pin_load`);
3. it takes as given a node state an MCU pin sets (`mcu_pin_state`) — the
   RS-485 fail-safe claim assumes DE/RE is low, which a floating pin during
   reset does not guarantee.

A claim that does not say what it measures keeps the netlist-wide X6 rule,
so D2 can only be narrowed by a declaration, never by an omission.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from core.ir_examples import IR_001, IR_003
from generators.netlist.spice import SpiceNetlistGenerator
from generators.protocol import ClaimScope, EnvelopeDecision, PortContract, grid_of
from generators.realize import realize
from proof.dependence import mcu_elements_reached, measured_nodes
from proof.netlist import parse
from test_simulation_accuracy import _skip_no_ngspice
from validation.claims import assess, derive_mcu_models, graded
from validation.defeaters import REGISTER
from validation.grid_adapters import ADAPTERS, board_cases, simulate

LED = """* LED on a Thevenin pin
V_VCC_5V vcc_5v 0 DC 5.0
V_PIN_LED_CTRL led_ctrl_src 0 DC 5.0
R_PIN_LED_CTRL led_ctrl_src led_ctrl 25.0
R_MCU_U1 vcc_5v 0 100
D_LED1 led_anode 0 DLED
R_R1 led_ctrl led_anode 1540.0
C_C1 vcc_5v 0 1e-7
.op
.model DLED D (Is=3.2e-19 N=2)
.end
"""

RS485 = """* RS-485 bus, MCU on the rail only
V_VCC_3V3 vcc_3v3 0 DC 3.135
R_MCU_U1 vcc_3v3 0 41
R_LOAD_U2 vcc_3v3 0 12000
R_R1 rs485_a rs485_b 120.0
R_R2 vcc_3v3 rs485_a 332.0
R_R3 rs485_b 0 332.0
R_TIE_RS485_DE_RE rs485_de_re 0 1G
.op
.end
"""


# ── Route 1: the symbolic check itself ──────────────────────────────────────

class TestSymbolicDependence:
    def test_the_pin_model_reaches_the_led_current_and_the_supply_resistor_does_not(self):
        assert mcu_elements_reached(LED, "diode_current(D_LED1)") == ("R_PIN_LED_CTRL", "V_PIN_LED_CTRL")
        assert mcu_elements_reached(LED, "series_power(R_R1,D_LED1)") == ("R_PIN_LED_CTRL", "V_PIN_LED_CTRL")

    def test_the_supply_resistor_reaches_the_rail_current_and_no_node_voltage(self):
        # Across an ideal source it sets only that source's current.
        assert mcu_elements_reached(LED, "i(V_VCC_5V)") == ("R_MCU_U1",)
        assert mcu_elements_reached(LED, "v(vcc_5v)") == ()
        assert mcu_elements_reached(RS485, "i(V_VCC_3V3)") == ("R_MCU_U1",)

    def test_nothing_on_the_rs485_bus_depends_on_the_mcu(self):
        for q in ("vdiff(rs485_a,rs485_b)", "rth(rs485_a,rs485_b)", "power(R_R1)"):
            assert mcu_elements_reached(RS485, q) == (), q

    def test_a_diode_between_the_element_and_the_quantity_does_not_hide_it(self):
        # The stand-in keeps the network's structure: the load sees the pin
        # through the diode, so it depends on the pin.
        net = ("* through a diode\nV_PIN_X x_src 0 DC 5\nR_PIN_X x_src x 25\n"
               "D_D1 x y DD\nR_L y 0 1000\n.model DD D (Is=1e-14 N=1)\n.end\n")
        assert mcu_elements_reached(net, "v(y)") == ("R_PIN_X", "V_PIN_X")

    def test_an_unknown_node_or_element_is_an_error_not_independence(self):
        with pytest.raises(KeyError):
            mcu_elements_reached(RS485, "v(nowhere)")
        with pytest.raises(KeyError):
            mcu_elements_reached(RS485, "i(V_NOWHERE)")

    def test_measured_nodes(self):
        assert measured_nodes(LED, "series_power(R_R1,D_LED1)") == {"led_ctrl", "led_anode"}
        assert measured_nodes(LED, "i(V_VCC_5V)") == {"vcc_5v"}
        assert measured_nodes(RS485, "vdiff(rs485_a,rs485_b)") == {"rs485_a", "rs485_b"}


# ── The library, every CI case ──────────────────────────────────────────────

MCU_CASES = [(n, b) for n, b in board_cases() if b is not None]
PASSIVE_CASES = [(n, b) for n, b in board_cases() if b is None]


def _case(name, board):
    adapter = ADAPTERS[name].build(board)
    point = next(iter(grid_of(adapter.generator, board).points()))
    intent = IntentIR(requirements=adapter.intent_for(point).requirements,
                      provenance=Provenance(producer=Producer.FORM))
    circuit = realize(adapter.generator, intent)
    cov = circuit.validation_coverage
    if cov.get("properties_hash"):
        circuit = realize(adapter.generator, intent.sign_off("test", properties_hash=cov["properties_hash"]))
    return adapter.generator, intent, circuit


_CACHE: Dict[Tuple[str, str], tuple] = {}


def case(name, board):
    if (name, board) not in _CACHE:
        _CACHE[(name, board)] = _case(name, board)
    return _CACHE[(name, board)]


def claims(name, board) -> Dict[str, dict]:
    return {c["id"]: c for c in case(name, board)[2].validation_coverage["claims"]}


def models(claim) -> List[str]:
    return [p for p in claim["scope"]["model"].split("+") if p.startswith("mcu_")]


RS485_CASES = [c for c in MCU_CASES if c[0] == "rs485_node"]
DHT_CASES = [c for c in MCU_CASES if c[0] == "dht22_node"]
LED_CASES = [c for c in MCU_CASES if c[0] == "led_indicator"]


class TestTheThreeRoutes:
    @pytest.mark.parametrize("name,board", RS485_CASES)
    def test_the_rs485_bus_claims_the_mcu_cannot_reach_are_released(self, name, board):
        rows = claims(name, board)
        for cid in ("rs485.driver_load", "proof.rs485.driver_load", "rs485.termination_dissipation"):
            assert "D2" not in rows[cid]["defeaters"], cid
            assert models(rows[cid]) == [], cid

    @pytest.mark.parametrize("name,board", RS485_CASES)
    def test_the_failsafe_claim_keeps_d2_through_its_assumed_pin_state(self, name, board):
        # Idle means the driver is off — DE/RE low — and nothing but the MCU
        # pin holds it there. Route 3, inherited by the proof.
        rows = claims(name, board)
        for cid in ("rs485.failsafe_bias", "proof.rs485.failsafe_bias"):
            assert "D2" in rows[cid]["defeaters"], cid
            assert models(rows[cid]) == ["mcu_pin_state"], cid
            assert rows[cid]["scope"]["assumes"] == ["RS485_DE_RE"], cid

    @pytest.mark.parametrize("name,board", DHT_CASES)
    def test_the_dht22_pullup_check_is_structural(self, name, board):
        row = claims(name, board)["dht.pullup_present"]
        assert row["defeaters"] == [] and row["verdict"] == "holds"
        assert row["scope"]["model"] == "design_graph"

    @pytest.mark.parametrize("name,board", DHT_CASES)
    def test_the_dht22_line_claims_keep_d2_for_the_unmodelled_pin(self, name, board):
        # The MCU's own pin sits on DATA and the netlist has nothing for it.
        rows = claims(name, board)
        for cid in ("dht.rise_time", "dht.sink_current", "proof.dht.rise_time", "proof.dht.sink_current"):
            assert "D2" in rows[cid]["defeaters"], cid
            assert models(rows[cid]) == ["mcu_pin_load"], cid

    @pytest.mark.parametrize("name,board", MCU_CASES)
    def test_rail_currents_name_the_boards_supply_model(self, name, board):
        rows = claims(name, board)
        rail = {"led_indicator": "led.rail_current", "dht22_node": "dht.rail_current",
                "rs485_node": "rs485.rail_current"}[name]
        netlist = SpiceNetlistGenerator().generate(case(name, board)[2])
        ohms = next(float(l.split()[3]) for l in netlist.splitlines() if l.startswith("R_MCU_"))
        assert f"mcu_as_{ohms:g}R" in models(rows[rail])
        assert "D2" in rows[rail]["defeaters"]

    @pytest.mark.parametrize("name,board", LED_CASES)
    def test_led_claims_name_the_pin_model_and_not_the_supply_resistor(self, name, board):
        for cid, row in claims(name, board).items():
            if row["scope"] and row["scope"]["model"] != "design_graph" and cid != "led.rail_current":
                assert models(row) == ["mcu_pin_thevenin"], cid
                assert "D2" in row["defeaters"], cid

    @pytest.mark.parametrize("name,board", PASSIVE_CASES)
    def test_passive_designs_cite_no_d2(self, name, board):
        for cid, row in claims(name, board).items():
            assert "D2" not in row["defeaters"], cid

    @pytest.mark.parametrize("name,board", MCU_CASES + PASSIVE_CASES)
    def test_every_behavioural_claim_says_what_it_measures_and_derives_cleanly(self, name, board):
        # No claim on a CI case falls back to the netlist-wide rule: each has
        # measures, and re-deriving from them reproduces the models on its scope.
        generator, intent, circuit = case(name, board)
        netlist = SpiceNetlistGenerator().generate(circuit)
        bench = {p.quantity: tuple(b.line for b in p.bench) for p in generator.properties(intent)}
        for cid, row in claims(name, board).items():
            scope = row["scope"]
            if not scope or scope["model"] == "design_graph":
                continue
            assert scope["measures"], cid
            derived = derive_mcu_models(circuit, netlist, [(q, bench.get(q, ())) for q in scope["measures"]],
                                        scope["assumes"])
            assert list(derived) == models(row), cid

    def test_the_released_count_on_the_ci_cases(self):
        # 42 citations before, 9 released: driver load (Stage 3 and proof) and
        # terminator dissipation on RS-485, the pull-up check on DHT22 — all x3.
        cited = sum("D2" in r["defeaters"] for n, b in MCU_CASES for r in claims(n, b).values() if r["critical"])
        assert cited == 33


class _Declares:
    """A generator whose one claim measures what the test says."""

    name = "declares"
    version = "0.0.1"
    function = "declares"

    def __init__(self, measures=(), assumes=(), model="mna_ideal"):
        self.scope = ClaimScope(model=model, measures=tuple(measures), assumes=tuple(assumes))

    def envelope(self, intent):
        return EnvelopeDecision.accept((PortContract(name="P", direction="input"),))

    def claims(self, intent):
        return [graded("c", "a claim", True, "monotone_corners", self.scope, defeaters=("D1",))]


def _row(generator, circuit):
    return next(c for c in assess(generator, object(), circuit).claims if c.id == "c")


class TestDeclarationsDecide:
    def test_a_claim_that_declares_nothing_keeps_the_netlist_wide_rule(self):
        row = _row(_Declares(), IR_001)                    # IR_001 carries R_MCU_U1
        assert "mcu_as_100R" in row.scope.model and "D2" in row.defeaters

    def test_a_declared_measure_the_mcu_cannot_reach_is_released(self):
        row = _row(_Declares(measures=("v(vcc_5v)",)), IR_001)
        assert "mcu_" not in row.scope.model and "D2" not in row.defeaters

    def test_a_declared_measure_on_an_unmodelled_mcu_pin_cites_d2(self):
        node = next(c.node_id for c in IR_001.connections
                    if c.component_id == "U1" and c.node_id.startswith("DHT"))
        row = _row(_Declares(measures=(f"v({node.lower()})",)), IR_001)
        assert "mcu_pin_load" in row.scope.model and "D2" in row.defeaters

    def test_an_assumed_mcu_pin_state_cites_d2(self):
        node = next(c.node_id for c in IR_001.connections
                    if c.component_id == "U1" and c.node_id.startswith("DHT"))
        row = _row(_Declares(measures=("v(vcc_5v)",), assumes=(node,)), IR_001)
        assert "mcu_pin_state" in row.scope.model and "D2" in row.defeaters

    def test_an_unreadable_declaration_falls_back_rather_than_releasing(self):
        row = _row(_Declares(measures=("v(nowhere)",)), IR_001)
        assert "mcu_as_100R" in row.scope.model and "D2" in row.defeaters

    def test_a_design_without_an_mcu_never_cites_d2(self):
        assert "D2" not in _row(_Declares(measures=("v(out)",)), IR_003).defeaters
        assert "D2" not in _row(_Declares(), IR_003).defeaters


class TestSignaturesDoNotMove:
    def test_the_statement_hash_does_not_read_the_mcu_models(self):
        # D2's derivation changed; what a user signed did not. A signature on a
        # design from before this change still matches.
        generator, intent, circuit = case("rs485_node", "arduino_uno")
        from validation.claims import prove_properties

        proved = prove_properties(generator, intent, circuit)
        statement = proved[0].statement
        moved = statement.model_copy(update={"mcu_models": ("something_else",)})
        assert moved.hash == statement.hash

    def test_the_register_names_all_four_representations(self):
        doubt = REGISTER["D2"].doubt
        for name in ("mcu_as_100R", "mcu_pin_thevenin", "mcu_pin_load", "mcu_pin_state"):
            assert name in doubt


# ── Route 1 against ngspice ──────────────────────────────────────────────────

def _perturb(netlist: str, supply: bool, pin: bool) -> str:
    out = []
    for line in netlist.splitlines():
        parts = line.split()
        if supply and line.startswith("R_MCU_"):
            parts[3] = repr(float(parts[3]) * 3)
        elif pin and line.startswith("R_PIN_"):
            parts[3] = repr(float(parts[3]) * 3)
        elif pin and line.startswith("V_PIN_"):
            parts[4] = repr(float(parts[4]) * 0.9)
        out.append(" ".join(parts) if parts else line)
    return "\n".join(out) + "\n"


def _observe(data, netlist: str, quantity: str):
    """The operating-point numbers a quantity is a function of, or None if .op cannot see it."""
    kind, args = re.match(r"^(\w+)\((.*)\)$", quantity).group(1), quantity[quantity.index("(") + 1:-1].split(",")
    v = lambda n: 0.0 if n == "0" else data.dc_voltages[n.lower()]
    parsed = parse(netlist)
    try:
        if kind == "v":
            return (v(args[0]),)
        if kind == "vdiff":
            return (v(args[0]) - v(args[1]),)
        if kind == "i":
            return (data.branch_currents[args[0].lower()],)
        if kind in ("power", "diode_current"):
            e = parsed.element(args[0])
            return (v(e.a) - v(e.b),)
        if kind == "series_power":
            r, d = parsed.element(args[0]), parsed.element(args[1])
            return (v(r.a) - v(r.b), v(d.a) - v(d.b))
    except KeyError:
        return None   # a proof's test-bench element (V_PROBE, C_BUS): not in the design netlist
    return None       # rth, cutoff, rise_time: not operating-point quantities


def _moved(a, b) -> bool:
    return any(not math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-12) for x, y in zip(a, b))


@_skip_no_ngspice
class TestRouteOneAgainstNgspice:
    """
    Independent of the symbolic path: ngspice solves the real nonlinear
    circuit. A claim names `mcu_as_<R>R` exactly when its quantity moves with
    the supply resistor, and `mcu_pin_thevenin` exactly when it moves with the
    pin model — neither missed nor invented.
    """

    @pytest.mark.parametrize("name,board", MCU_CASES)
    def test_named_models_are_exactly_the_ones_that_move_the_quantity(self, name, board):
        circuit = case(name, board)[2]
        netlist = SpiceNetlistGenerator().generate(circuit)
        base = simulate(netlist)
        runs = {"supply": simulate(_perturb(netlist, True, False)),
                "pin": simulate(_perturb(netlist, False, True))}
        checked = 0
        for cid, row in claims(name, board).items():
            scope = row["scope"]
            if not scope or scope["model"] == "design_graph":
                continue
            seen = [(_observe(base, netlist, q), q) for q in scope["measures"]]
            if any(o is None for o, _ in seen):
                continue
            moved = {k: any(_moved(o, _observe(run, netlist, q)) for o, q in seen) for k, run in runs.items()}
            named = models(row)
            assert moved["supply"] == any(m.startswith("mcu_as_") for m in named), cid
            assert moved["pin"] == ("mcu_pin_thevenin" in named), cid
            if moved["supply"] or moved["pin"]:
                assert "D2" in row["defeaters"], cid
            checked += 1
        # Not vacuous: the claims an operating point can see were all compared.
        # DHT22's line claims use test-bench elements, so only its rail is seen.
        assert checked >= {"led_indicator": 8, "rs485_node": 4, "dht22_node": 1}[name]
