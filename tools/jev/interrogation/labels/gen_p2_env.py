"""P2 — install environment: IEC 60664-1 pollution degree and overvoltage category.

Truth from the published definitions (IEC 60664-1 as quoted by TI SLLA353A and TI SLUP419): pollution
degree from the micro-environment the board's insulation sees; overvoltage category from how the board is
powered relative to the mains installation. `need_more_information` where the description omits the
deciding fact. The B14 template's combined env_label is asked too, scored against a PD-only mapping.
"""
from common import cite, pick_subset, write_set

QUESTIONS = {
    "env_label": {  # B14 template, verbatim
        "type": "choice",
        "instructions": "Which install environment does the user's description indicate?",
        "criteria": {
            "pd2_ovc2_indoor_controlled": "Indoor, controlled, occasional condensation.",
            "pd3_ovc3_field_wired": "Field-wired, conductive pollution possible.",
            "pd1_sealed": "Sealed enclosure, no conductive pollution.",
            "need_more_information": "The description does not determine it.",
        },
    },
    "pollution_degree": {
        "type": "choice",
        "instructions": "Which IEC 60664-1 pollution degree applies to the environment the board's insulation is exposed to?",
        "criteria": {
            "pd1": "No pollution or only dry, nonconductive pollution occurs. The pollution has no influence.",
            "pd2": "Only nonconductive pollution occurs. However, a temporary conductivity caused by condensation is to be expected.",
            "pd3": "Conductive pollution occurs or dry non-conductive pollution occurs which becomes conductive due to condensation which is to be expected.",
            "pd4": "Continuous conductivity occurs due to conductive dust, rain, or other wet conditions.",
            "need_more_information": "The description does not determine the pollution degree.",
        },
    },
    "overvoltage_category": {
        "type": "choice",
        "instructions": "Which IEC 60664-1 overvoltage category applies to how the board is powered?",
        "criteria": {
            "ovc_i": "Circuits connected in a way that takes measures to limit overvoltage transients.",
            "ovc_ii": "Equipment supplied from a fixed installation.",
            "ovc_iii": "Equipment with a fixed installation subject to special requirements.",
            "ovc_iv": "Equipment used at the origin of installation, connected directly to the mains voltage.",
            "need_more_information": "The description does not determine the overvoltage category.",
        },
    },
}

# (id, pd, ovc, description, derivation)
ITEMS = [
    ("E01", "pd2", "ovc_ii", "The controller sits in a climate-controlled office inside a plastic desktop case. It plugs into a 230 V wall socket and its mains power supply is on the board.",
     "Office, occasional condensation only (PD2, TI SLUP419 'offices'); plugged into an outlet (OVC II, TI SLUP419)."),
    ("E02", "pd2", "ovc_i", "A thermostat board on a living-room wall, powered from the furnace's 24 VAC step-down transformer.",
     "Indoor home (PD2); TI SLUP419 names 24-VAC thermostats fed through a step-down transformer as Category I."),
    ("E03", "pd3", "ovc_iii", "The board goes in a ventilated machine cabinet on a metal-stamping shop floor, where metal dust gets in. The cabinet is hardwired to the plant's 400 V three-phase distribution.",
     "Conductive metal dust reaches the board (PD3); industrial machinery hardwired to the mains (OVC III, TI SLUP419)."),
    ("E04", "pd1", "ovc_i", "The board is potted in epoxy inside a hermetically sealed housing and runs from a 3.6 V lithium battery.",
     "Sealed to exclude dust and moisture (PD1, TI SLUP419); no mains connection, battery circuit with no transient source (OVC I)."),
    ("E05", "pd4", "ovc_i", "The board is fixed, with no enclosure, to the outside wall of a cattle shed where rain and snow reach it. It is powered from a 24 VAC Class 2 transformer located indoors.",
     "Rain and snow on the board (PD4); fed through a step-down transformer (OVC I per TI SLUP419's example)."),
    ("E06", "pd2", "ovc_iii", "The module mounts inside a sub-distribution board (fuse panel) in a heated office building; its supply is wired directly to the busbar through a breaker.",
     "Heated indoor (PD2); inside a fuse panel, permanently connected (OVC III, TI SLUP419 'switches within a fuse panel')."),
    ("E07", "pd3", "ovc_ii", "A plug-in controller (230 V cord and plug) for a workbench in an unheated farm workshop where condensation is expected.",
     "Unheated farm room with expected condensation (PD3, TI SLUP419 'farming equipment and unheated factory rooms'); plugged in (OVC II)."),
    ("E08", "pd2", "ovc_iv", "The board is part of a utility electricity meter at the service entrance of a house, in a dry indoor basement, powered from the incoming supply before the main breaker.",
     "Dry indoor (PD2); electricity meter at the origin of the installation (OVC IV, TI SLUP419)."),
    ("E09", "pd1", "ovc_ii", "The board is sealed in a gasketed IP68 enclosure with a desiccant pack that excludes dust and moisture; the enclosure plugs into a 120 V outlet through a sealed cord.",
     "Sealed to exclude dust and moisture (PD1); plugged into an outlet (OVC II)."),
    ("E10", "pd3", "ovc_i", "A zone controller mounted in the service compartment of a rooftop air-handling unit; the compartment takes in outdoor air and condensation is expected. It is powered from the unit's 24 VAC control transformer.",
     "Condensation expected (PD3); fed through a step-down control transformer (OVC I per TI SLUP419's 24-VAC example)."),
    ("E11", "pd2", "ovc_ii", "A benchtop instrument board for a university electronics lab, supplied through a detachable IEC mains cord.",
     "Lab (PD2, TI SLUP419 'labs'); cord-connected to an outlet (OVC II)."),
    ("E12", "pd3", "ovc_iii", "A controller hardwired to the 230 V supply of a commercial kitchen hood, installed in the hood's control box, where grease-laden steam condenses every day.",
     "Non-conductive grease that becomes conductive with expected condensation (PD3 definition); permanently connected (OVC III)."),
    ("E13", "pd4", "ovc_iii", "A controller hardwired to the 400 V mains of an outdoor irrigation pump station, mounted on an open terminal frame with no enclosure, exposed to rain.",
     "Rain on the board (PD4); hardwired to fixed installation (OVC III)."),
    ("E14", "pd2", "ovc_i", "The signal-processing board inside a home DVD player; the player's own power supply board sits between it and the mains.",
     "Home (PD2); TI SLLA353 gives 'circuit board inside a DVD player' as Category I (signal level)."),
    ("E15", "pd3", "ovc_iii", "The control board of an air conditioner's outdoor unit, hardwired to the building supply; the electronics bay is vented and condensation forms in it.",
     "Condensation expected (PD3); air conditioner hardwired to mains (OVC III, TI SLUP419)."),
    ("E16", "pd2", "ovc_ii", "The main board of an office laser printer that plugs into a wall socket.",
     "Office (PD2); plugged in (OVC II)."),
    ("E17", "pd1", "ovc_i", "A conformal-coated board inside a sealed, dry enclosure in a server room, powered from a 12 V SELV supply with transient suppression.",
     "Sealed/conformal coated so no condensation reaches it (PD1, TI SLUP419); protected low-voltage supply limits transients (OVC I)."),
    ("E18", "pd3", "ovc_ii", "A plug-in 230 V controller for an unheated factory storage room.",
     "Unheated factory room (PD3, TI SLUP419); plugged in (OVC II)."),
    ("E19", "pd2", "ovc_iii", "A DIN-rail module in a heated, clean electrical room, hardwired into the building's distribution board.",
     "Heated clean indoor (PD2); permanently connected in the fixed installation (OVC III)."),
    ("E20", "pd4", "ovc_i", "A sensor board with no housing on the open deck of a ship, soaked by spray, powered from a 12 V SELV supply that includes transient suppression.",
     "Continuous wetting (PD4); protected low-voltage supply (OVC I)."),
    ("E21", "pd2", "ovc_iv", "The communications module inside a smart electricity meter in a dry indoor meter room, powered from the meter's supply at the service entrance.",
     "Dry indoor (PD2); electricity meter at the origin (OVC IV)."),
    ("E22", "pd3", "ovc_iv", "A surge monitor mounted at the service entrance, the origin of a farm building's installation, inside an unheated barn.",
     "Unheated farm building (PD3); origin of installation (OVC IV)."),
    ("E23", "nmi", "ovc_ii", "A controller that plugs into a 230 V wall socket. The customer has not said where it will be used.",
     "Location and enclosure unknown (PD: need more information); plugged in (OVC II)."),
    ("E24", "pd2", "nmi", "A board for a home living room. The customer has not said how it will be powered.",
     "Home (PD2); power connection unknown (OVC: need more information)."),
    ("E25", "nmi", "nmi", "A controller for a customer's product. No information yet about where it goes or how it is powered.",
     "Neither location nor power stated."),
    ("E26", "nmi", "ovc_iii", "A board that will be hardwired to a 230 V distribution circuit; the installation site has not been stated.",
     "Site unknown (PD: NMI); hardwired (OVC III)."),
    ("E27", "pd3", "nmi", "A board to be mounted in an unheated barn where condensation is common; the power arrangement is still to be decided.",
     "Unheated barn with condensation (PD3); power unknown (OVC: NMI)."),
    ("E28", "nmi", "ovc_i", "A board powered from a 24 VAC Class 2 step-down transformer; the enclosure and the site are unknown.",
     "Site unknown (PD: NMI); step-down transformer (OVC I)."),
    ("E29", "nmi", "nmi", "A Wi-Fi relay board the customer describes as 'for home or industrial use', powered by 'whatever the installer has'.",
     "Both dimensions left open."),
    ("E30", "nmi", "ovc_ii", "A board for a residential garage; nobody has said whether the garage is heated. It plugs into an outlet.",
     "Heated garage would be PD2, unheated with condensation PD3: not determined (NMI); plugged in (OVC II)."),
    ("E31", "pd1", "ovc_iii", "A board encapsulated in a potted, sealed module that is permanently wired into an industrial machine's 400 V supply.",
     "Potted and sealed (PD1); hardwired industrial machinery (OVC III)."),
    ("E32", "pd2", "ovc_i", "The board in a battery-powered handheld meter used in offices.",
     "Office (PD2); battery circuit, no mains (OVC I)."),
    ("E33", "pd3", "ovc_i", "The board in a supermarket refrigerated display case's electronics bay, where condensation forms during every defrost; it is powered from a 24 VAC Class 2 transformer.",
     "Condensation expected (PD3); step-down transformer (OVC I)."),
    ("E34", "pd4", "ovc_iii", "A controller hardwired to a building's 230 V distribution circuit, mounted in an unsealed junction frame on an exterior wall where rain and snow reach the board.",
     "Rain and snow on the board (PD4); hardwired (OVC III)."),
    ("E35", "pd2", "ovc_ii", "A smart-speaker board in a bedroom, plugged into the wall.",
     "Home (PD2); plugged in (OVC II)."),
    ("E36", "pd3", "ovc_iii", "A board in a food-processing plant's washdown area, inside a vented (not sealed) enclosure where condensation occurs daily; permanently wired to the plant's 480 V distribution.",
     "Daily condensation in an industrial area (PD3); hardwired (OVC III)."),
]

PARAPHRASES = {
    "E01": "Where it goes: an air-conditioned office, in a plastic box on a desk. Power: a mains cord into a 230 V socket; the power supply is on this board.",
    "E03": "Location: a metal-stamping plant; the cabinet is ventilated and fine metal dust settles inside. Power: permanently wired to 400 V three-phase distribution.",
    "E04": "Epoxy-potted inside a hermetic case; powered by a 3.6 V lithium cell; no mains anywhere.",
    "E07": "Farm workshop, not heated, condensation expected on cold mornings. The unit has a 230 V plug.",
    "E08": "This board lives in the utility's electricity meter where the supply enters the house (dry basement), and it is fed from the incoming line ahead of the main breaker.",
    "E10": "Installed in a rooftop air handler's service bay that breathes outdoor air, so condensation is expected; supply is the unit's own 24 VAC control transformer.",
    "E13": "Pump station outdoors; the board is on an open, unenclosed terminal frame that gets rained on; it is hardwired to 400 V mains.",
    "E17": "Sealed dry enclosure, board conformal-coated, in a server room; 12 V SELV supply with surge suppression.",
    "E20": "Mounted bare on a ship's open deck and regularly soaked by spray; powered by a 12 V SELV supply with transient suppression.",
    "E23": "Mains-plug (230 V) controller; installation location not given.",
    "E28": "Supplied by a 24 VAC Class 2 step-down transformer; no word yet on enclosure or site.",
    "E33": "Electronics bay of a refrigerated display case in a supermarket; condensation forms at each defrost; 24 VAC Class 2 transformer supply.",
}

TEMPLATE_MAP = {"pd1": "pd1_sealed", "pd2": "pd2_ovc2_indoor_controlled", "pd3": "pd3_ovc3_field_wired",
                "pd4": None, "nmi": "need_more_information"}


def main():
    items = []
    for iid, pd, ovc, desc, why in ITEMS:
        pd_t = "need_more_information" if pd == "nmi" else pd
        ovc_t = "need_more_information" if ovc == "nmi" else ovc
        item = {"id": f"P2-{iid}", "state": {"install_description": desc},
                "truth": {"pollution_degree": pd_t, "overvoltage_category": ovc_t, "env_label": TEMPLATE_MAP[pd]},
                "derivation": why}
        if iid in PARAPHRASES:
            item["paraphrase_state"] = {"install_description": PARAPHRASES[iid]}
        items.append(item)
    ids = [i["id"] for i in items]
    write_set("p2_env", {
        "task": "P2 install environment (IEC 60664-1 pollution degree + overvoltage category; B14 env_label)",
        "questions": QUESTIONS,
        "truth_rule": ("Pollution degree and overvoltage category are set from the IEC 60664-1 definitions as quoted by "
                       "TI SLLA353A and the examples in TI SLUP419. PD refers to the micro-environment the board sees "
                       "(sealed/potted/conformal-coated -> PD1). need_more_information when the description omits the "
                       "deciding fact. env_label (B14 template) truth maps from PD only: pd1->pd1_sealed, "
                       "pd2->pd2_ovc2_indoor_controlled, pd3->pd3_ovc3_field_wired, pd4->no correct class (excluded "
                       "from env_label accuracy), NMI->need_more_information."),
        "stricter_option": {
            "order": {"pollution_degree": ["pd1", "pd2", "pd3", "pd4"], "overvoltage_category": ["ovc_i", "ovc_ii", "ovc_iii", "ovc_iv"]},
            "defaults": {"industrial": {"pollution_degree": "pd3", "overvoltage_category": "ovc_iii"},
                         "indoor": {"pollution_degree": "pd2", "overvoltage_category": "ovc_ii"}},
            "rule": ("final = max(Jev argmax, default) per dimension; a need_more_information argmax yields the default. "
                     "Unsafe error = final below truth on a determinate dimension. Over-design = final above truth."),
        },
        "citations": cite("TI_SLLA353", "TI_SLUP419", "TEMPLATE_B14"),
        "variants": {
            "repeat_subset": pick_subset(ids, 9, "p2_repeat"),
            "paraphrase_subset": sorted(i["id"] for i in items if "paraphrase_state" in i),
            "blind_subset": pick_subset(ids, 3, "p2_blind"),
        },
        "items": items,
    })


if __name__ == "__main__":
    main()
