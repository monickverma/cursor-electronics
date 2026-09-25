"""P3 — RS-485 isolation: stated ground-potential difference (GPD) against the -7 V..+12 V common-mode range.

Computed truth. A half-duplex RS-485 bus is bidirectional, so each node's driver (outputs 0..Vcc, Vcc <= 5 V,
relative to its own ground) is seen by the other node's receiver shifted by the GPD. TI SLLA070 gives the
common-mode range (-7 V to 12 V) and the resulting ground-difference limit ("its maximum limit of +/-7 V ...
a potential close to +12 V can exist ... assuming VCC = 5 V"). Truth: |GPD| <= 6.5 V -> within_range;
|GPD| >= 10 V -> exceeds_range. 8-9 V is a gray zone where a V_CM-average model (driver common mode ~Vcc/2)
and the per-line model disagree; those items are scored separately. Undeclared GPD -> 'undeclared'.
"""
from common import cite, pick_subset, write_set

CHOICE = {
    "isolation_label": {
        "type": "choice",
        "instructions": "Given what the description says about the ground-potential difference (GPD) between the RS-485 nodes, which applies?",
        "criteria": {
            "within_range": "The stated worst-case GPD keeps every receiver's A and B inputs within the RS-485 -7 V to +12 V common-mode range.",
            "exceeds_range": "The stated worst-case GPD can push a receiver's A or B input outside the -7 V to +12 V range.",
            "undeclared": "The description does not state the ground-potential difference.",
        },
    }
}
DECLARED_NOULS = {
    "gpd_exceeds": {"type": "noul", "instructions": "Can the stated worst-case ground-potential difference push the voltage at a receiver's A or B input outside the RS-485 -7 V to +12 V common-mode range?"},
    "gpd_within": {"type": "noul", "instructions": "Does the stated worst-case ground-potential difference keep the voltage at every receiver's A and B inputs inside the RS-485 -7 V to +12 V common-mode range?"},
}
UNDECLARED_NOULS = {
    "isolation_needed": {"type": "noul", "instructions": "With ground-potential difference undeclared, could it exceed the RS-485 -7 V to +12 V common-mode range in this install?"},  # B14 verbatim
    "stays_within": {"type": "noul", "instructions": "With ground-potential difference undeclared, will it stay within the RS-485 -7 V to +12 V common-mode range in this install?"},
}

# Declared items: (id, |GPD| V, transceiver Vcc, wording of the install and the GPD statement)
DECLARED = [
    ("D01", 0.5, 5.0, "Master and one slave in two cabinets 30 m apart on the same floor. Measured worst-case ground difference between the cabinets, including switching transients: 0.5 V."),
    ("D02", 1.0, 3.3, "Gateway and sensor node on 3.3 V transceivers, 80 m apart in one warehouse. The ground of either node can sit up to 1 V above or below the other's."),
    ("D03", 1.5, 5.0, "Three nodes along a 120 m run inside one factory hall. Commissioning measured at most 1.5 V between any two node grounds, transients included."),
    ("D04", 2.0, 5.0, "Master PLC and a VFD's Modbus port, 40 m apart; the installer logged a 2 V worst-case ground offset between them."),
    ("D05", 3.0, 3.3, "Two 3.3 V nodes on different floors of an office building. Worst-case ground-potential difference: 3 V."),
    ("D06", 4.0, 5.0, "A rooftop unit controller and the BMS master, 150 m of cable. The contractor's survey found up to 4 V between the two grounds during compressor starts."),
    ("D07", 5.0, 5.0, "Master and slave in adjacent buildings sharing one earthing system; worst-case difference between node grounds measured at 5 V."),
    ("D08", 5.5, 3.3, "A 3.3 V sensor node and the gateway, 200 m apart. Worst-case ground difference: 5.5 V, either polarity."),
    ("D09", 6.0, 5.0, "Two nodes in separate panels fed from different distribution boards in one plant. The ground of one can sit up to 6 V above or below the other's."),
    ("D10", 6.5, 5.0, "Pump controller and plant master, 250 m apart. Worst-case measured ground-potential difference, including motor-start transients: 6.5 V."),
    ("D11", 10.0, 5.0, "Master and slave in two buildings 300 m apart. Worst-case ground-potential difference between them: 10 V."),
    ("D12", 12.0, 3.3, "A 3.3 V node on a remote tank and the master in the control room. The remote ground can sit up to 12 V above or below the master's."),
    ("D13", 15.0, 5.0, "Nodes in two separate buildings on different service transformers; the survey recorded 15 V between the node grounds during a fault test."),
    ("D14", 20.0, 5.0, "Master and a slave on a motor skid 150 m away. Ground-potential difference during motor starts: up to 20 V."),
    ("D15", 24.0, 5.0, "A node on a crane and the master on the ground floor. Worst-case ground difference: 24 V."),
    ("D16", 30.0, 3.3, "Two 3.3 V nodes in buildings 500 m apart. Measured worst-case GPD: 30 V."),
    ("D17", 48.0, 5.0, "Master in the main building, slave in a pump house fed from its own transformer. Worst-case GPD: 48 V."),
    ("D18", 60.0, 5.0, "A wind-turbine base node and the site master, 400 m apart. The GPD can reach 60 V during switching."),
    ("D19", 120.0, 5.0, "Two nodes on separate utility services; a ground fault can raise one ground by up to 120 V relative to the other."),
    ("D20", 400.0, 5.0, "A substation node and the plant master. Under fault conditions the node ground can rise up to 400 V relative to the master."),
    ("G01", 8.0, 5.0, "Master and slave in two cabinets on separate supplies; worst-case GPD measured at 8 V."),
    ("G02", 9.0, 5.0, "Two nodes 350 m apart in different buildings; worst-case GPD 9 V."),
]

# Undeclared items: (id, plausibly_exceeds, install wording)
UNDECLARED = [
    ("N01", True, "Master in the plant office building, slave in a pump house 600 m away across the yard. Each building has its own service transformer. Nobody has measured the ground difference."),
    ("N02", True, "An RS-485 link between two buildings on a campus. The cable runs outdoors on poles and each building has its own earthing. The ground difference is unknown."),
    ("N03", True, "A node at the base of a wind-turbine tower and the master in the site control building 400 m away. Ground difference not stated."),
    ("N04", True, "Master in a factory control room; a slave on a VFD-driven motor skid 150 m away, where heavy motor currents flow in the shared protective earth. GPD not measured."),
    ("N05", False, "Master and three slaves are all inside one control panel, powered from a single 24 VDC supply with one common ground; the bus is 3 m long. No GPD figure is given."),
    ("N06", False, "Two boards stacked in one enclosure share the same 5 V regulator and ground plane; the RS-485 cable between them is 20 cm. No GPD figure is given."),
    ("N07", False, "A sensor node and its gateway sit on the same bench, both powered from the same USB hub; the cable is 2 m. No GPD figure is given."),
    ("N08", False, "Four DIN-rail modules side by side on one rail in one cabinet, all fed by one 24 V supply and sharing its 0 V; the bus is a 1 m jumper chain. No GPD figure is given."),
]

PARAPHRASES = {
    "D02": "Transceivers run at 3.3 V. The gateway and the sensor node are 80 m apart in a warehouse, and their grounds differ by no more than 1 V in either direction.",
    "D05": "Office building, two 3.3 V nodes on different floors; the largest ground-potential difference between them is 3 V.",
    "D09": "One plant, two panels, two distribution boards: either node's ground may be as much as 6 V above or below the other's.",
    "D11": "Buildings 300 m apart, one master and one slave; the ground-potential difference can reach 10 V.",
    "D14": "A slave sits on a motor skid 150 m from the master; when the motors start, the two grounds can differ by as much as 20 V.",
    "D17": "The slave's pump house has its own transformer; between it and the master's building the ground difference can reach 48 V.",
    "D20": "During a fault, the substation node's ground may rise as much as 400 V above the plant master's.",
    "N01": "Pump house 600 m from the plant office across a yard, two separate service transformers, no measurement of the difference between the two grounds.",
    "N06": "Same enclosure, same 5 V regulator, same ground plane; 20 cm of RS-485 cable; nothing is said about ground difference.",
    "N08": "One cabinet, one DIN rail, one 24 V supply whose 0 V all four modules share, 1 m of jumpers; the ground difference is not mentioned.",
}


def within(gpd):
    return gpd <= 6.5


def main():
    items = []
    for iid, gpd, vcc, text in DECLARED:
        gray = 7.0 < gpd < 10.0
        label = None if gray else ("within_range" if within(gpd) else "exceeds_range")
        item = {"id": f"P3-{iid}", "kind": "gray" if gray else "declared",
                "state": {"bus": "RS-485 half-duplex Modbus RTU, non-isolated transceivers", "transceiver_supply_v": vcc, "install": text},
                "questions": {**CHOICE, **DECLARED_NOULS},
                "truth": {"isolation_label": label,
                          "gpd_exceeds": None if gray else (not within(gpd)),
                          "gpd_within": None if gray else within(gpd)},
                "gpd_v": gpd,
                "derivation": (f"|GPD| = {gpd:g} V. Receiver inputs span GPD + [0, {vcc:g}] V relative to the receiver ground, both directions: "
                               + ("gray zone (per-line model exceeds, V_CM model within)" if gray else
                                  ("inside -7..+12 V" if within(gpd) else "outside -7..+12 V")))}
        if iid in PARAPHRASES:
            item["paraphrase_state"] = {**item["state"], "install": PARAPHRASES[iid]}
        items.append(item)
    for iid, large, text in UNDECLARED:
        item = {"id": f"P3-{iid}", "kind": "undeclared",
                "state": {"bus": "RS-485 half-duplex Modbus RTU, non-isolated transceivers", "transceiver_supply_v": 5.0, "install": text},
                "questions": {**CHOICE, **UNDECLARED_NOULS},
                "truth": {"isolation_label": "undeclared", "isolation_needed": large, "stays_within": not large},
                "derivation": ("GPD not stated -> 'undeclared'. Plausibility label for the B14 Noul from TI SLLA070 "
                               "(long-distance links between separately earthed sites need isolation; GPD up to kilovolts) "
                               "and TI SLLA370 (isolation manages ground-potential differences): "
                               + ("separate buildings/transformers/earths or heavy PE currents -> could exceed" if large else
                                  "single supply and single ground, short cable -> no GPD source"))}
        if iid in PARAPHRASES:
            item["paraphrase_state"] = {**item["state"], "install": PARAPHRASES[iid]}
        items.append(item)
    ids = [i["id"] for i in items]
    write_set("p3_isolation", {
        "task": "P3 isolation need: stated GPD vs RS-485 -7..+12 V common-mode range (computed), plus undeclared GPD",
        "questions_note": "Declared items ask isolation_label + gpd_exceeds/gpd_within (polarity pair); undeclared items ask isolation_label + the B14 isolation_needed Noul (verbatim) + stays_within (polarity pair).",
        "question_sets": {"declared": {**CHOICE, **DECLARED_NOULS}, "undeclared": {**CHOICE, **UNDECLARED_NOULS}},
        "truth_rule": ("|GPD| <= 6.5 V -> within_range; |GPD| >= 10 V -> exceeds_range (both the per-line model and the "
                       "V_CM-average model agree there); 8-9 V gray (excluded from primary accuracy). GPD not stated -> "
                       "undeclared. isolation_needed (B14) truth = plausibility by construction: separate "
                       "buildings/transformers/earths or heavy PE current -> True; one supply, one ground, short cable -> False."),
        "stricter_option": ("Design is isolated unless the governing label is a stable, confirmed within_range. Policies "
                            "evaluated offline: (a) Jev-only: isolate iff argmax != within_range; (b) Jev + gate: drop "
                            "isolation only if argmax == within_range with p_top >= 0.9 in every variant; (c) deterministic: "
                            "compute from a declared GPD, isolate when undeclared. Unsafe = not isolated when truth is "
                            "exceeds_range or undeclared."),
        "citations": cite("TI_SLLA070", "TI_SLLA370", "TEMPLATE_B14", "JEV_JAGGEDNESS"),
        "variants": {
            "repeat_subset": pick_subset(ids, 8, "p3_repeat"),
            "paraphrase_subset": sorted(i["id"] for i in items if "paraphrase_state" in i),
            "blind_subset": pick_subset(ids, 3, "p3_blind"),
        },
        "items": items,
    })


if __name__ == "__main__":
    main()
