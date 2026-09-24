"""
Every design the library accepts keeps its own claims — off the CI grid too.

The grid tests (`test_generator_library.py`) check 27 points. The Stage 3 + 4
verification fuzzed a few hundred more and found three accepted designs that
carried a failed claim of their own: an RC filter behind a source that moved
f_c past tolerance, an LED whose R1 could overheat at 17 mA, and every LED
above 5.0 V failing its voltage-rating rule. This file keeps that corpus: a
seeded, reproducible sample of requirements, in and out of envelope, and the
invariant that anything accepted is realised cleanly —

- no claim fails, and nothing is "not assessed";
- every Stage 4 property is proven;
- every ValidationRule is accounted for exactly once;
- realising twice gives the same bytes.
"""

import math
import random

import pytest

from core.intent_ir import IntentIR, Producer, Provenance
from core.ir_schema import ValidationRule
from generators.realize import canonical_json, realize
from generators.registry import default_registry

REGISTRY = default_registry()
PER_FUNCTION = 20
RULES = {f"rule.{r.value}" for r in ValidationRule}
FUNCTIONS = ("low_pass_filter", "voltage_divider", "led_indicator", "temperature_humidity_sensor",
             "modbus_rtu_master")


def _requirements(rng: random.Random, function: str) -> dict:
    def logu(a, b):
        return round(math.exp(rng.uniform(math.log(a), math.log(b))), rng.choice([1, 2, 3]))

    def r(a, b, d=3):
        return round(rng.uniform(a, b), d)

    t, c, p = {}, {}, {}
    if function == "low_pass_filter":
        t["cutoff_hz"] = logu(10, 2e5)
        if rng.random() < .5:
            t["tolerance_pct"] = r(1, 20, 1)
        c["supply_v"] = r(1, 16, 2)
        if rng.random() < .6:
            c["source_impedance_ohm"] = r(0, 5000, 0)
        if rng.random() < .2:
            c["pinned"] = rng.choice([{"R1": "4.7k"}, {"R1": "1.5k"}, {"C1": "10n"}, {"C1": "100n"}])
    elif function == "voltage_divider":
        c["supply_v"] = r(1, 50, 2)
        t["vout_v"] = r(0.02, c["supply_v"], 3)
        if rng.random() < .5:
            c["divider_current_ma"] = logu(0.01, 10)
        if rng.random() < .4:
            c["load_ohm"] = logu(1e3, 1e7)
        if rng.random() < .2:
            c["pinned"] = {"R1": rng.choice(["1k", "4.7k", "10k"]), "R2": rng.choice(["1k", "4.7k", "10k"])}
    elif function == "led_indicator":
        t["led_current_ma"] = r(0.5, 25, 2)
        c["supply_v"] = r(4.6, 5.4, 2)
        if rng.random() < .3:
            p["gpio_pin"] = rng.choice(["D2", "D9", "D13"])
        if rng.random() < .2:
            c["pinned"] = {"R1": rng.choice(["150", "220", "330", "1k"])}
    elif function == "temperature_humidity_sensor":
        c["supply_v"] = r(4.3, 5.7, 2)
        c["cable_length_m"] = r(0, 25, 1)
        if rng.random() < .2:
            c["pinned"] = {"R1": rng.choice(["4.7k", "10k", "2.2k"])}
    else:
        c["supply_v"] = r(4.4, 5.6, 2)
        if rng.random() < .4:
            c["far_end_terminated"] = rng.random() < .5
        if rng.random() < .2:
            v = rng.choice(["470", "680", "1k"])
            c["pinned"] = {"R2": v, "R3": v}
    return {"function": function, "targets": t, "constraints": c, "preferences": p}


def _corpus():
    rng = random.Random(20260923)
    for function in FUNCTIONS:
        for i in range(PER_FUNCTION):
            yield pytest.param(_requirements(rng, function), id=f"{function}-{i}")


@pytest.mark.parametrize("requirements", list(_corpus()))
def test_an_accepted_design_keeps_its_own_claims(requirements):
    intent = IntentIR(requirements=requirements, provenance=Provenance(producer=Producer.FORM))
    dispatch = REGISTRY.dispatch(intent)
    if not dispatch.accepted:
        # A refusal is a fine outcome — and must say why.
        assert all(r.reason for r in dispatch.refusals)
        return
    g = dispatch.generator
    design = realize(g, intent)
    coverage = design.validation_coverage
    failing = [(c["id"], c["detail"]) for c in coverage["claims"] if c["verdict"] == "fails"]
    assert not failing, failing
    assert not coverage["not_assessed"], coverage["not_assessed"]
    assert [p["status"] for p in coverage["properties"]] == ["proven"] * len(coverage["properties"])
    rules = [c["id"] for c in coverage["claims"] if c["id"].startswith("rule.")]
    assert sorted(rules) == sorted(RULES)
    assert canonical_json(design) == canonical_json(realize(g, intent))


def test_the_corpus_reaches_every_generator():
    rng = random.Random(20260923)
    accepted = set()
    for function in FUNCTIONS:
        for _ in range(PER_FUNCTION):
            intent = IntentIR(requirements=_requirements(rng, function),
                              provenance=Provenance(producer=Producer.FORM))
            dispatch = REGISTRY.dispatch(intent)
            if dispatch.accepted:
                accepted.add(dispatch.generator.name)
    assert accepted == {g.name for g in REGISTRY.generators}
