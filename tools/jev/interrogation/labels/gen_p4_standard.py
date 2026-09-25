"""P4 — standard-family triage (UL 60730 / UL 61010-2-201 / UL 508A panel / none) and possibly-life-safety.

Truth from the standards' published scopes:
- UL/IEC 60730-1: automatic electrical controls in, on or with household and similar equipment (electricity, gas,
  oil...), incl. building-automation controls and controls for commercial catering, heating and air-conditioning (DLS).
- UL/IEC 61010-2-201: control equipment — PLCs/PACs, DCS components, remote I/O, industrial PCs, PADTs, HMIs —
  for command and control of machines, automated manufacturing and industrial processes (Panasonic; UL whitepaper).
- UL 508A: industrial control panels — assemblies of two or more power/control circuit components in an enclosure
  or on a sub-panel, general industrial use, <= 1000 V; incl. panels for flame safety supervision (ULSE scope 1.1-1.3).
  Fire-alarm control units (UL 864) and emergency lighting (UL 924) are excluded from 508A (scope 1.11, 1.13).
- none_apparent: the product falls under none of the three (e.g., IT/AV, lab measurement, medical, toys).
Life safety by construction: the board performs or directly interfaces a function whose purpose is protecting people
from fire, explosion, toxic gas or loss of life support (gas valves/burner supervision, fire detection/alarm/
suppression, hood exhaust interlocks, emergency lighting, smoke control, CO ventilation, infusion pumps).
"""
from common import cite, pick_subset, write_set

QUESTIONS = {
    "standard_family_flag": {  # B14 verbatim
        "type": "choice",
        "instructions": "Which standard family should a person review for this board?",
        "criteria": {
            "ul_60730": "Automatic electrical control for household or similar use.",
            "ul_61010_2_201": "Programmable controller.",
            "ul_508a_panel_only": "The board is a component of an industrial control panel.",
            "none_apparent": "No listed family apparent.",
            "need_more_information": "Product use is unclear.",
        },
    },
    "possibly_life_safety": {  # B14 verbatim
        "type": "noul",
        "instructions": "Could this board's failure plausibly affect life safety (gas valves, fire suppression, hood exhaust)?",
    },
    "no_life_safety_effect": {  # polarity pair
        "type": "noul",
        "instructions": "Is this board's failure limited to comfort, convenience, process or property consequences, with no plausible effect on life safety?",
    },
}

# (id, family truth or 'contested', life_safety truth True/False/None(unknown), description, note)
ITEMS = [
    ("S01", "ul_60730", False, "A wall thermostat for a home heat pump. It senses room temperature and switches the heat pump's 24 VAC heating and cooling call relays.", "Household automatic control (60730)."),
    ("S02", "ul_60730", False, "The control board inside a household refrigerator that runs the compressor and the defrost heater from the cabinet temperature.", "Household appliance control (60730)."),
    ("S03", "ul_60730", False, "A demand-controlled ventilation controller for an office building's air handler: it reads CO2 and sets the supply-fan speed, and it is part of the building automation system.", "Building-automation control within ISO 16484 (60730-1 scope)."),
    ("S04", "ul_60730", True, "A boiler controller that sequences a gas burner: ignition, flame supervision through a flame rod, and opening the main gas valve.", "Control for gas-fired household/similar equipment (60730); gas valve and flame supervision -> life safety."),
    ("S05", "ul_60730", False, "A humidistat that switches the humidifiers in a commercial greenhouse.", "Automatic control for similar/commercial use (60730)."),
    ("S06", "ul_60730", False, "An electronic timer that switches a household water heater's element on a schedule.", "Household automatic control (60730)."),
    ("S07", "ul_60730", False, "A supermarket refrigerated display-case controller that runs the case's expansion valve and defrost cycles and reports alarms to the store system.", "Commercial refrigeration control (60730-1 extended scope)."),
    ("S08", "ul_60730", True, "The ignition and valve controller of a household gas fireplace, which opens the gas valve after proving the pilot flame.", "Household gas-appliance control (60730); gas valve -> life safety."),
    ("S09", "ul_61010_2_201", False, "A programmable logic controller CPU module that runs ladder logic for a packaging machine and drives its I/O modules.", "PLC (61010-2-201)."),
    ("S10", "ul_61010_2_201", False, "A DIN-rail remote I/O module with 16 x 24 V digital inputs for a bottling line's sensors, reporting to a PLC over Modbus RTU.", "Remote I/O component (61010-2-201)."),
    ("S11", "ul_61010_2_201", False, "An HMI touch panel mounted on an injection-molding machine, where operators set process parameters.", "HMI for machine control (61010-2-201)."),
    ("S12", "ul_61010_2_201", False, "An industrial PC that supervises a CNC cell and sends part programs to the machine controllers.", "Industrial computer for machine control (61010-2-201)."),
    ("S13", "ul_61010_2_201", False, "A programmable automation controller for a paper mill's winder line.", "PAC (61010-2-201)."),
    ("S14", "ul_61010_2_201", False, "An analog I/O module with 4-20 mA inputs and outputs that plugs into a PLC backplane, for process control in a food factory.", "PLC I/O module (61010-2-201)."),
    ("S15", "ul_61010_2_201", False, "A distributed-control-system controller node that runs a brewery's fermentation temperature loops.", "DCS component (61010-2-201)."),
    ("S16", "ul_61010_2_201", False, "A stand-alone programmable controller board for automating a bottle-labeling machine; the customer programs it in structured text.", "Programmable controller for a machine (61010-2-201)."),
    ("S17", "ul_508a_panel_only", False, "A relay interface board that will be mounted on the back-plate of a conveyor line's industrial control panel, alongside the main breaker, motor starters and terminal blocks, built by a panel shop.", "Component of an industrial control panel assembly (508A 1.3)."),
    ("S18", "ul_508a_panel_only", False, "A terminal-block breakout board for a pump-station control panel that an integrator assembles with contactors and overload relays inside a steel enclosure.", "Component of an industrial control panel (508A 1.3)."),
    ("S19", "ul_508a_panel_only", False, "A power-monitoring board installed inside a factory's industrial control panel next to the PLC and the drives; it is one component of the panel assembly.", "Component of an industrial control panel (508A)."),
    ("S20", "ul_508a_panel_only", False, "An opto-isolated I/O board mounted on the sub-panel of a packaging line's control panel; the panel builder will label the finished panel to UL 508A.", "Component on a sub-panel (508A 1.3); names the standard."),
    ("S21", "ul_508a_panel_only", False, "An alarm-indicator board mounted in the door of a compressor-room industrial control panel and wired to the panel's control relays.", "Component of an industrial control panel (508A)."),
    ("S22", "ul_508a_panel_only", True, "A board mounted inside a burner-management panel (an industrial control panel for flame-safety supervision of a boiler) that relays the flame-scanner signal.", "508A 1.2 covers panels for flame safety supervision; flame supervision -> life safety."),
    ("S23", "none_apparent", False, "A USB-powered desk lamp with touch dimming.", "Not an automatic control, PLC or panel."),
    ("S24", "none_apparent", False, "A battery-powered LED blinker kit for students learning to solder.", "Educational kit; none of the three."),
    ("S25", "none_apparent", False, "The input front-end board of a bench oscilloscope for an electronics lab.", "Laboratory measurement equipment (IEC 61010-1 family, not -2-201)."),
    ("S26", "none_apparent", False, "The amplifier board of a Bluetooth speaker.", "Audio/IT equipment (not listed)."),
    ("S27", "none_apparent", False, "The main board of a home Wi-Fi router.", "IT equipment (not listed)."),
    ("S28", "none_apparent", False, "A portable GPS bike computer.", "Consumer electronics (not listed)."),
    ("S29", "none_apparent", True, "The control board of a hospital infusion pump.", "Medical electrical equipment (not listed); loss of dosing control -> life safety."),
    ("S30", "none_apparent", True, "The controller of an emergency exit sign and emergency lighting unit that switches to battery when mains fails.", "Emergency lighting (UL 924, excluded from 508A by 1.13) -> life safety."),
    ("S31", "none_apparent", True, "The main board of a building's fire-alarm control unit.", "Fire-alarm control unit (UL 864, excluded from 508A by 1.11) -> life safety."),
    ("S32", "need_more_information", None, "An ESP32 board with four relays. The customer calls it a 'general controller' and has not said what it will switch.", "Use unknown."),
    ("S33", "need_more_information", None, "A board that reads temperatures and switches a 230 V output. The application has not been described.", "Use unknown."),
    ("S34", "need_more_information", None, "The customer wants 'a control board for our system'. No other details yet.", "Use unknown."),
    ("S35", "need_more_information", None, "A relay board 'for automation' that the customer says could end up in homes or in factories.", "Use unknown."),
    ("S36", "need_more_information", None, "A 24 V I/O board whose end product has not been decided.", "Use unknown."),
    ("S37", "contested", True, "A commercial kitchen hood controller: it runs the exhaust fan while cooking, interlocks the gas valve for the appliances under the hood, and shuts the gas off when the fire-suppression system trips.", "Family contested (60730 catering control vs 508A panel); gas valve, suppression and hood exhaust -> life safety."),
    ("S38", "contested", True, "A controller that closes the gas shut-off valve for a restaurant's cooking line when the hood's fire-suppression system discharges.", "Family contested; gas valve + suppression -> life safety."),
    ("S39", "contested", True, "A smoke-damper controller for a building's smoke-control system.", "Family contested (smoke control equipment); life safety."),
    ("S40", "contested", True, "A parking-garage ventilation controller that starts the exhaust fans when carbon monoxide exceeds a threshold.", "Family contested; toxic-gas ventilation -> life safety."),
]

PARAPHRASES = {
    "S01": "Home heat-pump thermostat on the wall: measures the room and closes the 24 VAC heat or cool call relay.",
    "S03": "In an office building's building-automation system, this board adjusts the air handler's supply fan from a CO2 reading (demand-controlled ventilation).",
    "S04": "Gas boiler burner sequencer: lights the burner, supervises the flame with a flame rod, and opens the main gas valve.",
    "S09": "Packaging machine PLC: the CPU module that executes ladder logic and commands the machine's I/O modules.",
    "S11": "Operator touch screen (HMI) fixed to an injection-molding machine for entering process settings.",
    "S17": "Panel-shop build for a conveyor line: this relay interface board goes on the control panel's back-plate next to the breaker, starters and terminal blocks.",
    "S22": "Inside a boiler's burner-management (flame-safety) control panel, this board passes the flame scanner's signal on.",
    "S25": "Front-end board of a lab bench oscilloscope.",
    "S30": "Emergency exit sign / emergency light controller that transfers to battery on mains failure.",
    "S32": "Four-relay ESP32 'general controller'; what it switches is not known.",
    "S37": "Kitchen hood controller for a restaurant: exhaust fan during cooking, gas-valve interlock for the cooking appliances, gas cut-off when the suppression system fires.",
    "S40": "Garage ventilation: when CO passes a set level, this board starts the exhaust fans.",
}


def main():
    items = []
    for iid, fam, ls, desc, note in ITEMS:
        item = {"id": f"P4-{iid}", "state": {"product_description": desc},
                "truth": {"standard_family_flag": None if fam == "contested" else fam,
                          "possibly_life_safety": ls, "no_life_safety_effect": None if ls is None else (not ls)},
                "family_contested": fam == "contested", "derivation": note}
        if iid in PARAPHRASES:
            item["paraphrase_state"] = {"product_description": PARAPHRASES[iid]}
        items.append(item)
    ids = [i["id"] for i in items]
    write_set("p4_standard", {
        "task": "P4 standard-family triage + possibly-life-safety (B14 questions verbatim + polarity Noul)",
        "questions": QUESTIONS,
        "truth_rule": ("Family from the published scopes (see module docstring and citations). 'contested' items have a "
                       "family that reasonable reviewers could set differently; they are excluded from family accuracy "
                       "and kept for life safety. Life-safety truth by the construction rule in the docstring; None = "
                       "use unknown (scored only for whether the >0.1 review rule fires)."),
        "stricter_option": "possibly_life_safety > 0.1 -> mandatory person review (B14 mapping); also evaluated at 0.5.",
        "literal_reading_note": ("The B14 criterion texts are terse: 'household or similar use' vs the 60730-1 extension to "
                                 "commercial/building-automation controls, and 'Programmable controller' vs the 61010-2-201 "
                                 "scope that includes HMIs, industrial PCs and remote I/O. Items S03, S05, S07 (commercial) and "
                                 "S10-S12 (I/O, HMI, IPC) test whether Jev reads the label names literally."),
        "citations": cite("DLS_60730", "PANASONIC_61010_2_201", "UL_61010_2_201_SEARCH", "ULSE_508A", "PRODUCT_MASTER", "TEMPLATE_B14"),
        "variants": {
            "repeat_subset": pick_subset(ids, 10, "p4_repeat"),
            "paraphrase_subset": sorted(i["id"] for i in items if "paraphrase_state" in i),
            "blind_subset": pick_subset(ids, 3, "p4_blind"),
        },
        "items": items,
    })


if __name__ == "__main__":
    main()
