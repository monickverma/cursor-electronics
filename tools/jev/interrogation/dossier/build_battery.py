"""build_battery.py — the question battery for the big-file interrogation, with pre-registered labels.

Writes (next to this file):
  battery.json         every question: key, chunk, category, Jev question object, ground truth where one exists
  prereg_labels.json   the labelled subset: ground truth, how each label was derived, answer section and
                       character offset(s) in the original-order full dossier, in_core flag; agent priors
Ground truth comes from the dossier text (itself built from the repo), from code, or from construction
(absent-answer needles) — never from Jev. Run build_dossier.py first.
"""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REQ = HERE.parents[1] / "requests"
FULL = (HERE / "circuit_os_dossier.md").read_text(encoding="utf-8")
CORE = (HERE / "circuit_os_dossier_core.md").read_text(encoding="utf-8")
SECS = json.loads((HERE / "dossier_sections.json").read_text(encoding="utf-8"))["sections"]
CORE_IDS = {s["id"] for s in SECS if s["core"]}
NMI = "need_more_information"
NMI_NEEDLE = "Choose when the state does not contain the answer."
NMI_DECIDE = "Choose when a fact missing from the state would change the answer."

Q = []  # battery rows


def section_of(offset):
    """Section id containing a character offset of the original full dossier."""
    best = None
    for s in SECS:
        pos = FULL.find(f"## [{s['id']}] ")
        if pos != -1 and pos <= offset:
            best = s["id"]
    return best


def anchors(text):
    import re
    pat = re.compile(r"\s+".join(re.escape(w) for w in text.split()))
    return [{"offset": m.start(), "rel": round(m.start() / len(FULL), 4), "section": section_of(m.start())}
            for m in pat.finditer(FULL)]


def needle(key, section, question, options, correct, anchor, wk=False):
    """Present-answer comprehension choice. options: dict label -> description (NMI appended)."""
    crit = dict(options)
    crit[NMI] = NMI_NEEDLE
    hits = anchors(anchor)
    assert hits, f"{key}: anchor not found: {anchor!r}"
    assert section in {h["section"] for h in hits}, f"{key}: anchor not in {section}: {hits}"
    Q.append({"key": key, "chunk": "A", "category": "needle", "sub": "present", "type": "choice",
              "q": {"type": "choice", "instructions": question, "criteria": crit},
              "gt": correct, "gt_derivation": f"dossier text {section}: {anchor!r}",
              "section": section, "anchor": anchor, "anchor_hits": hits, "multi": len(hits) > 1,
              "in_core": " ".join(anchor.split()) in " ".join(CORE.split()), "world_knowledge": wk})


def absent(key, question, options, why):
    crit = dict(options)
    crit[NMI] = NMI_NEEDLE
    Q.append({"key": key, "chunk": "A", "category": "needle", "sub": "absent", "type": "choice",
              "q": {"type": "choice", "instructions": question, "criteria": crit},
              "gt": NMI, "gt_derivation": f"by construction: {why}", "section": None, "in_core": False})


def absent_noul(key, question, why):
    Q.append({"key": key, "chunk": "A", "category": "needle", "sub": "absent_noul", "type": "noul",
              "q": {"type": "noul", "instructions": question},
              "gt": "0.25<=p<=0.75", "gt_derivation": f"by construction: {why}", "section": None, "in_core": False})


def polarity(pid, section, yes_q, no_q, truth_yes, anchor):
    hits = anchors(anchor)
    assert hits, f"{pid}: anchor not found: {anchor!r}"
    for suffix, text, truth in (("pos", yes_q, truth_yes), ("neg", no_q, not truth_yes)):
        Q.append({"key": f"{pid}_{suffix}", "chunk": "A", "category": "needle", "sub": "polarity", "type": "noul",
                  "pair": pid, "q": {"type": "noul", "instructions": text},
                  "gt": bool(truth), "gt_derivation": f"dossier text {section}: {anchor!r}",
                  "section": section, "anchor": anchor, "anchor_hits": hits, "multi": len(hits) > 1,
                  "in_core": " ".join(anchor.split()) in " ".join(CORE.split())})


def choice(key, chunk, category, instructions, criteria, ref=None, ref_derivation=None, prior=None, meta=None):
    crit = dict(criteria)
    if NMI not in crit:
        crit[NMI] = NMI_DECIDE
    Q.append({"key": key, "chunk": chunk, "category": category, "type": "choice",
              "q": {"type": "choice", "instructions": instructions, "criteria": crit},
              "ref": ref, "ref_derivation": ref_derivation, "prior": prior, **(meta or {})})


def noul(key, chunk, category, instructions, ref=None, ref_derivation=None, meta=None, criteria=None):
    q = {"type": "noul", "instructions": instructions}
    if criteria:
        q["criteria"] = criteria
    Q.append({"key": key, "chunk": chunk, "category": category, "type": "noul", "q": q,
              "ref": ref, "ref_derivation": ref_derivation, **(meta or {})})


def score(key, chunk, category, instructions, levels, ref=None, ref_derivation=None, prior=None, meta=None):
    Q.append({"key": key, "chunk": chunk, "category": category, "type": "score",
              "q": {"type": "score", "instructions": instructions, "criteria": levels},
              "ref": ref, "ref_derivation": ref_derivation, "prior": prior, **(meta or {})})


# ============================================================ A. needles (present answers)
needle("n01_licence", "S04", "Under which licence is Circuit OS released?",
       {"MIT": "The MIT licence.", "Apache-2.0": "The Apache 2.0 licence.", "AGPL-3.0": "The GNU AGPL 3.0.",
        "GPL-2.0": "The GNU GPL 2.0."}, "AGPL-3.0", "AGPL-3.0")
needle("n02_credits", "S04", "Which LLM access route had its credits exhausted on 2026-09-23?",
       {"OpenRouter": "OpenRouter.", "Anthropic_direct": "The Anthropic API called directly.",
        "Azure_OpenAI": "Azure OpenAI.", "vLLM_on_ROCm": "A self-hosted vLLM server on AMD ROCm."},
       "OpenRouter", "AI via OpenRouter (credits exhausted 2026-09-23)")
needle("n03_trust_top", "S03", "Which source ranks highest in the project's trust hierarchy?",
       {"tests_and_simulation": "Test results and simulation outputs.", "source_code_ast": "Source code via AST scan.",
        "derived_yaml_json": "progress.yaml and state.json.", "brain_markdown": "The brain/*.md files."},
       "tests_and_simulation", "highest first: test results + simulation outputs")
needle("n04_explainer_text", "S02", "Per the rules, what must the explainer's free-text handling find?",
       {"first_text_block": "The first text block of the response.", "last_tool_use_block": "The last tool_use block.",
        "thinking_block": "The model's thinking block.", "json_schema": "A JSON schema object."},
       "first_text_block", "Explainer free-text must find first text block")
needle("n05_version_conflict", "S02", "What HTTP status does a patch version conflict return?",
       {"409": "HTTP 409.", "422": "HTTP 422.", "503": "HTTP 503.", "429": "HTTP 429."}, "409", "409 version_conflict")
needle("n06_platformio", "S04", "Which PlatformIO version does the stack use?",
       {"6.2.0": "PlatformIO 6.2.0.", "5.3.0": "PlatformIO 5.3.0.", "7.1.3": "PlatformIO 7.1.3.",
        "20.0.0": "PlatformIO 20.0.0."}, "6.2.0", "PlatformIO 6.2.0")
needle("n07_flag_route", "S05", "Which route sits behind an experimental flag?",
       {"/pcb/compile": "POST /pcb/compile.", "/design/generate": "POST /design/generate.",
        "/design/{id}/sign-off": "POST /design/{id}/sign-off.", "/auth/login": "POST /auth/login."},
       "/pcb/compile", "/pcb/compile (experimental flag)")
needle("n08_dht22_function", "S07", "What FUNCTION name does the dht22_node generator declare?",
       {"temperature_humidity_sensor": "temperature_humidity_sensor", "dht22_reader": "dht22_reader",
        "environment_sensor": "environment_sensor", "humidity_node": "humidity_node"},
       "temperature_humidity_sensor", "| temperature_humidity_sensor |")
needle("n09_softwareserial", "S07", "On the Uno, which pins does the RS-485 firmware drive through SoftwareSerial?",
       {"D10_D11": "D10 and D11.", "D0_D1": "D0 and D1 (the hardware UART).", "D2_D3": "D2 and D3.",
        "D5_D6": "D5 and D6."}, "D10_D11", "SoftwareSerial on D10/D11")
needle("n10_revision_schema", "S08", "Which IntentIR SCHEMA_VERSION added the `revision` field?",
       {"2.0.0": "2.0.0", "2.1.0": "2.1.0", "2.2.0": "2.2.0", "3.0.0": "3.0.0"}, "2.1.0",
       "2.1.0 (Stage 2) added `revision`")
needle("n11_circuit_id", "S08", "How is a design's circuit_id derived?",
       {"uuid5_of_intent_id": "uuid5 of the intent's intent_id.", "random_uuid4": "A fresh random uuid4.",
        "hash_of_requirements": "A hash of the requirements.", "generator_name_version": "The generator's name@version."},
       "uuid5_of_intent_id", "`uuid5(namespace, intent_id)`")
needle("n12_bmc_grade", "S09", "Which grade does the method `bounded_model_check` map to?",
       {"G1": "G1", "G3": "G3", "G4": "G4", "G6": "G6"}, "G4", '"bounded_model_check": "G4"')
needle("n13_out_of_scope", "S09", "Which of these is on the declared out-of-scope list printed on every design?",
       {"manufacturing_yield": "Manufacturing yield.", "rs485_termination": "RS-485 termination.",
        "pin_assignment": "Pin assignment validity.", "i2c_pullups": "I2C pull-ups."},
       "manufacturing_yield", '("manufacturing_yield", "manufacturing yield")')
needle("n14_d6_status", "S10", "What status does defeater D6 have in the register?",
       {"open": "open", "deferred": "deferred", "eliminated": "eliminated", "not_yet_applicable": "not_yet_applicable"},
       "not_yet_applicable", "| not_yet_applicable |")
needle("n15_d4_eliminator", "S10", "What eliminates defeater D4 according to the register?",
       {"measured_authoring_cost": "Measured authoring cost per generator.",
        "bench_measurement": "A bench measurement agreeing within tolerance.",
        "criterion_12_review": "Criterion 12's review.", "user_sign_off": "A person signing the properties."},
       "measured_authoring_cost", "measured authoring cost per generator (Stage 3 onward)")
needle("n16_pi_digits", "S11", "To how many digits was the π bracket checked in the Stage 4 gates?",
       {"15": "15 digits.", "40": "40 digits.", "80": "80 digits.", "1000": "1000 digits."}, "80",
       "the bracket checked against π at 80 digits")
needle("n17_stm32_part", "S12", "Which exact STM32 part is on the chosen STM32 target board?",
       {"STM32F411CEU6": "STM32F411CEU6", "STM32F103C8T6": "STM32F103C8T6", "STM32F401RE": "STM32F401RE",
        "STM32F407VG": "STM32F407VG"}, "STM32F411CEU6", "WeAct Black Pill (STM32F411CEU6)")
needle("n18_figure_audit_found", "S13", "What defect did the D7 figure audit find?",
       {"rs485_terminator_tolerance": "The RS-485 1206 terminator was boxed with 0402 tolerance.",
        "led_vf_scale": "The LED forward voltage was off by a factor of ten.",
        "dht22_pullup_missing": "The DHT22 pull-up was missing.",
        "esp32_strap_pin": "An ESP32 strapping pin was used."},
       "rs485_terminator_tolerance", "found RS-485 1206 terminator boxed with 0402 tolerance")
needle("n19_crit4_value", "S14", "Which wrong value demonstrated Phase 1 criterion 4 (simulation fails on wrong values)?",
       {"1nF_capacitor": "A 1 nF capacitor.", "1M_resistor": "A 1 MΩ resistor.", "reversed_led": "A reversed LED.",
        "12V_supply": "A 12 V supply."}, "1nF_capacitor", "1nF capacitor → FAIL grade")
needle("n20_injected_error", "S14", "When a deliberate 5% error was injected into resistor emission, how many of the 34 accuracy tests failed?",
       {"0": "0 of 34.", "5": "5 of 34.", "13": "13 of 34.", "34": "34 of 34."}, "13", "fails 13 of the 34 tests")
needle("n21_abstention", "S15", "What false-acceptance result did the Stage 1 abstention corpus report?",
       {"0_of_200": "0 of 200.", "1_of_200": "1 of 200.", "13_of_34": "13 of 34.", "56_of_56": "56 of 56."},
       "0_of_200", "0/200 false accept")
needle("n22_deferred_gate", "S15", "Which Stage 2 acceptance gate was deferred with a trigger?",
       {"use_a_ds18b20": "\"Use a DS18B20 instead\" end to end.", "determinism": "Byte-identical determinism.",
        "idempotence": "Empty-patch idempotence.", "orphaned_annotations": "Orphaned annotations surfaced."},
       "use_a_ds18b20", "\"Use a DS18B20 instead\" end to end")
needle("n23_p5_worst", "S15", "In the Stage 0 grid gate, what was the worst deviation for seeded fault P5?",
       {"0.0000%": "0.0000%", "2%": "2%", "4.8403%": "4.8403%", "15%": "15%"}, "4.8403%", "worst 4.8403%")
needle("n24_waveform_lib", "S16", "Which library does PRODUCT_MASTER name for the Phase 2 simulation waveform viewer?",
       {"Plotly.js": "Plotly.js", "D3.js": "D3.js", "Chart.js": "Chart.js", "Recharts": "Recharts"},
       "Plotly.js", "Simulation waveform viewer (Plotly.js)")
needle("n25_iot_kpi", "S16", "What is PRODUCT_MASTER's Phase 2 KPI for average IoT node design time?",
       {"15_minutes": "Under 15 minutes.", "30_minutes": "Under 30 minutes.", "45_minutes": "Under 45 minutes.",
        "one_business_day": "Within one business day."}, "45_minutes", "Average IoT node design under 45 minutes")
needle("n26_team_price", "S17", "What does the Team tier cost?",
       {"29_per_month": "$29/month.", "49_per_month": "$49/month.", "99_per_seat_month": "$99/seat/month.",
        "custom": "Custom pricing."}, "99_per_seat_month", "**Team — $99/seat/month:**")
needle("n27_co2_sensor", "S17", "Which CO2 sensors does the DCV board description name?",
       {"SCD30_SCD41_or_Telaire_6004": "SCD30/SCD41 over I2C, or Telaire 6004 analog.", "MH-Z19": "MH-Z19.",
        "CCS811": "CCS811.", "SGP30": "SGP30."}, "SCD30_SCD41_or_Telaire_6004", "SCD30/SCD41 over I2C, or Telaire 6004 analog")
needle("n28_audit_standards", "S17", "Which standards is the Phase 3 audit trail described as ready for?",
       {"ISO_13485_26262": "ISO 13485/26262.", "ISO_9001": "ISO 9001.", "IEC_61508": "IEC 61508.", "UL_508A": "UL 508A."},
       "ISO_13485_26262", "Audit trail (ISO 13485/26262 ready)")
needle("n29_rs485_spacing", "S18", "In PCB_STRATEGY's RS-485 example, what minimum distance from the switching regulator is stated?",
       {"2mm": "2 mm.", "5mm": "5 mm.", "8mm": "8 mm.", "20mm": "20 mm."}, "8mm", "8mm from the switching regulator")
needle("n30_cad_step", "S18", "Which step of the CAD staircase does PCB_STRATEGY say is the one to build?",
       {"viewer": "Step 1, the viewer.", "annotated_viewer": "Step 2, the annotated viewer.",
        "constrained_editor": "Step 3, the constrained editor.", "general_cad": "Step 4, general CAD."},
       "annotated_viewer", "**Step 2 is the one to build, and it is uniquely yours.**")
needle("n31_layout_best", "S19", "In the competitor table, which tool is marked best in class at PCB layout?",
       {"Quilter": "Quilter.", "Flux.ai": "Flux.ai.", "Celus.io": "Celus.io.", "Circuit_OS": "Circuit OS itself."},
       "Quilter", "✅ best in class", wk=True)
needle("n32_flaky_commit", "S20", "At which commit did a regen report 409 passing and 1 failing with no code change?",
       {"f5fbd3d": "f5fbd3d", "2edfbc8": "2edfbc8", "e803a99": "e803a99", "94b61c1": "94b61c1"}, "f5fbd3d",
       "regen at `f5fbd3d` reported 409 / 1 failing")
needle("n33_idle_current", "S21", "What idle current does the proposed DE/RE pull-down add on the Uno when DE/RE is driven high?",
       {"0.33_mA": "0.33 mA.", "0.5_mA": "0.5 mA.", "5_mA": "5 mA.", "50_mA": "50 mA."}, "0.5_mA", "= 0.5 mA on Uno")
needle("n34_esp32_strap", "S21", "Which of these is listed as an ESP32 strapping pin?",
       {"GPIO12": "GPIO12.", "GPIO4": "GPIO4.", "GPIO21": "GPIO21.", "GPIO33": "GPIO33."}, "GPIO12",
       "ESP32 straps are GPIO0, 2, 5, 12, 15")
needle("n35_brain_commits", "S21", "How many of the last 40 commits on phase2-stage0 used the `brain:` prefix?",
       {"2": "2.", "7": "7.", "8": "8.", "40": "40."}, "7", "`brain:` (7)")
needle("n36_better_manners", "S22", "According to the decision log, what is 'a deletion with better manners'?",
       {"deferral_without_trigger": "A deferral without a trigger.", "substitute_criterion": "A criterion met by substitute.",
        "unregistered_module": "An unregistered module.", "silent_amendment": "A silent amendment."},
       "deferral_without_trigger", "A deferral without a trigger is a deletion with better manners.")
needle("n37_deleted_module", "S24", "Which module was deleted to remove the LLM → CircuitIR path?",
       {"ai/circuit_reasoner.py": "ai/circuit_reasoner.py", "ai/intent_parser.py": "ai/intent_parser.py",
        "ai/explainer.py": "ai/explainer.py", "generators/realize.py": "generators/realize.py"},
       "ai/circuit_reasoner.py", "`backend/ai/circuit_reasoner.py` is deleted")
needle("n38_pi_defeater", "S25", "What was EVIDENCE_CLASSES Table C's π defeater renumbered to in the register?",
       {"D4": "D4", "D6": "D6", "D8": "D8", "D9": "D9"}, "D8", "bracket it\") becomes **D8**")
needle("n39_rc_prob", "S26", "What probability did TypeSafe give `swamp_with_larger_r1` in the 2026-09-23 RC decision?",
       {"0.58": "0.58", "0.83": "0.83", "0.87": "0.87", "0.13": "0.13"}, "0.87", "**swamp_with_larger_r1 0.87**")
needle("n40_rc_band", "S27", "What is the proven band for the RC low-pass cutoff in the D1 bench sheet?",
       {"896Hz_1.12kHz": "896 Hz – 1.12 kHz.", "850_1150Hz": "850 – 1150 Hz.", "990Hz_1.01kHz": "990 Hz – 1.01 kHz.",
        "3.28_3.34V": "3.28 – 3.34 V."}, "896Hz_1.12kHz", "Proven band: **896 Hz – 1.12 kHz**")
needle("n41_generator_50ohm", "S27", "In the bench procedure, by how much does a signal generator's 50 Ω output move f_c?",
       {"0.2%": "0.2%", "1.4%": "1.4%", "5%": "5%", "15%": "15%"}, "1.4%", "50 Ω output moves f_c by 1.4%")
needle("n42_finding_scanner", "S28", "Which finding number in the earlier report is the One-Rule scanner hole?",
       {"1": "Finding 1.", "5": "Finding 5.", "8": "Finding 8.", "12": "Finding 12."}, "1",
       "| 1 | **One-Rule scanner hole**")
needle("n43_unregistered_count", "S28", "How many backend files does finding 6 list as absent from MODULES?",
       {"2": "2.", "7": "7.", "8": "8.", "26": "26."}, "7", "7 backend files absent from `MODULES`")
needle("n44_highest_runtime", "S29", "Which proposed runtime use does the earlier report mark as highest value?",
       {"R1_transcription_fidelity": "R1, transcription fidelity.", "R2_patch_op_faithfulness": "R2, patch-op faithfulness.",
        "R7_refusal_backlog": "R7, refusal backlog labelling.", "R11_substitute_ordering": "R11, substitute ordering."},
       "R1_transcription_fidelity", "R1 **Transcription fidelity** (highest value)")
needle("n45_waiver_label", "S29", "In the DRC waiver triage use (P6), which label forces review at any probability?",
       {"safety_relevant": "safety_relevant", "needs_review": "needs_review", "cosmetic": "cosmetic", "reject": "reject"},
       "safety_relevant", "`safety_relevant` forces review at any probability")
needle("n46_first_run_rs485", "S30", "In the first live Jev run, which label did Jev return for the RS-485 DE/RE pull-down?",
       {"add_as_default_now": "add_as_default_now", "add_as_opt_in_constraint": "add_as_opt_in_constraint",
        "defer_with_trigger": "defer_with_trigger", "do_not_add": "do_not_add"},
       "add_as_opt_in_constraint", "| RS-485 DE/RE pull-down | `add_as_opt_in_constraint` |")
needle("n47_ops_burden", "S30", "What ops_burden score did the first live run report for X7?",
       {"0.50_of_3": "0.50 out of 3.", "1.50_of_3": "1.50 out of 3.", "2.97_of_3": "2.97 out of 3.",
        "3.00_of_3": "3.00 out of 3."}, "2.97_of_3", "`ops_burden` 2.97/3")
needle("n48_rc_formula", "S31", "Which formula does the dossier give for the RC low-pass cutoff frequency?",
       {"1/(2πRC)": "f_c = 1 / (2π·R·C)", "1/(RC)": "f_c = 1 / (R·C)", "2πRC": "f_c = 2π·R·C",
        "R/(2πC)": "f_c = R / (2π·C)"}, "1/(2πRC)", "f_c = 1 / (2π × R × C)", wk=True)
needle("n49_divider_ref", "S31", "In the Phase 1 voltage-divider reference, what is V_out?",
       {"3.30_V": "3.30 V.", "5.00_V": "5.00 V.", "5.07_V": "About 5.07 V.", "6.00_V": "6.00 V."}, "5.07_V",
       "V_out ≈ 5.07V")

# ============================================================ A. needles whose answer is NOT in the dossier
absent("a01_cost_ceiling", "What per-generation cost ceiling has the owner set for explanations?",
       {"under_0.05": "Under $0.05.", "0.05_to_0.20": "$0.05 to $0.20.", "over_0.20": "Over $0.20."},
       "the dossier says the owner has not stated a cost ceiling")
absent("a02_vendor", "Which live-pricing vendor has the owner chosen?",
       {"Digikey": "Digikey.", "LCSC": "LCSC.", "Mouser": "Mouser.", "Octopart": "Octopart."},
       "the dossier says no vendor has been chosen")
absent("a03_bench_cutoff", "What -3 dB cutoff was measured on the bench for the 1 kHz RC design?",
       {"950Hz": "About 950 Hz.", "1.00kHz": "About 1.00 kHz.", "1.05kHz": "About 1.05 kHz.", "1.12kHz": "About 1.12 kHz."},
       "no bench measurement exists (D1 open; no oscilloscope)")
absent("a04_flaky_assertion", "Which assertion fails when the flaky accuracy test fails?",
       {"cutoff_frequency": "A cutoff-frequency comparison.", "divider_voltage": "A divider output voltage.",
        "led_current": "An LED current.", "ac_parse": "The AC magnitude parser."},
       "the dossier says the flake was never diagnosed")
absent("a05_v2_exit", "What does PHASE_2_PLAN_v2 list as the Phase 2 exit criteria?",
       {"d1_closed": "D1 closed by a bench session.", "stages_0_6_done": "Stages 0–6 done.",
        "three_paying_pilots": "Three paying pilot teams.", "criterion_12_met": "Criterion 12 met."},
       "PHASE_2_PLAN_v2 is not in the repository or the dossier")
absent("a06_hvac_answer", "What did the HVAC controls people say when asked whether they want finished boards or designs?",
       {"finished_boards": "They want finished boards.", "designs": "They want designs.", "mixed": "Opinions were mixed."},
       "no such conversation is recorded")
absent("a07_baud", "What Modbus RTU baud rate does the rs485_node firmware use?",
       {"9600": "9600 baud.", "19200": "19200 baud.", "38400": "38400 baud.", "115200": "115200 baud."},
       "the baud rate is not in the dossier")
absent("a08_d1_date", "On what date will the owner run the D1 bench session?",
       {"this_week": "This week.", "before_phase2_exit": "Before Phase 2 exit.", "after_phase3_start": "After Phase 3 starts."},
       "not scheduled; the owner decides")
absent("a09_terminator_price", "What static price does the BOM give for the RS-485 1206 120 Ω terminator?",
       {"0.01_usd": "About $0.01.", "0.10_usd": "About $0.10.", "0.50_usd": "About $0.50."},
       "prices are not in the dossier")
absent("a10_reviewer", "Which external engineer reviewed a generated explanation for criterion 12?",
       {"final_year_ee_student": "A final-year EE student.", "faculty_member": "A faculty member.",
        "forum_reviewer": "A reviewer from an electronics forum."},
       "no external engineer has read an explanation (criterion 12 unmet, D3 deferred)")
absent("a11_thinking_off_cost", "What does one explanation cost with thinking disabled?",
       {"0.02_usd": "About $0.02.", "0.05_usd": "About $0.05.", "0.10_usd": "About $0.10.", "0.20_usd": "About $0.20."},
       "the thinking-disabled fix is untried")
absent("a12_freerouting_version", "Which freerouting version will Phase 3 pin?",
       {"1.9": "1.9.x", "2.0": "2.0.x", "2.1": "2.1.x"}, "no freerouting version is named in the dossier")
absent("a13_authoring_cost", "What is the measured authoring cost per generator (the evidence D4 asks for)?",
       {"under_1_day": "Under one day.", "1_to_3_days": "One to three days.", "about_1_week": "About one week.",
        "over_2_weeks": "Over two weeks."}, "not measured; D4 open")
absent_noul("a14_noul_cost_ceiling", "Is the owner's per-generation cost ceiling for explanations above $0.10?",
            "the ceiling has not been stated")
absent_noul("a15_noul_hvac_boards", "Will the first HVAC controls customer want finished boards rather than designs?",
            "PCB_STRATEGY §9.3 is an untested hypothesis")
absent_noul("a16_noul_flake_seed", "Was the flaky accuracy test's failure caused by a seed-dependent parameter sweep?",
            "the flake was never diagnosed")

# ============================================================ A. polarity pairs (both must be read correctly)
polarity("p01_firmware", "S02", "Is firmware shown to the user only after it has passed a PlatformIO compile?",
         "Is firmware shown to the user before it has passed a PlatformIO compile?", True,
         "Firmware shown only after PlatformIO compile")
polarity("p02_flashed", "S20", "Has any board been flashed with generated firmware yet?",
         "Is it recorded that no board has been flashed yet?", False, "No board flashed")
polarity("p03_grade_method", "S09", "Is a claim's grade derived from its method through one table?",
         "Is a claim's grade typed by hand for each claim?", True, "through one table, never typed per claim")
polarity("p04_d2_close", "S10", "Is anything in Phase 2 scheduled to close defeater D2?",
         "Is it recorded that nothing in Phase 2 is scheduled to close defeater D2?", False,
         "nothing in Phase 2 is scheduled to close it")
polarity("p05_pricing_gate", "S13", "In Stage 6, is pricing allowed to gate validation?",
         "Is it a Stage 6 gate that pricing never gates validation?", False, "pricing never gates validation")
polarity("p06_crit12", "S14", "Is Phase 1 criterion 12 (an external engineer reads an explanation cold) met?",
         "Is Phase 1 criterion 12 (an external engineer reads an explanation cold) unmet?", False, "**⏳ NOT MET**")
polarity("p07_gerber_phase3", "S17", "Is Gerber export listed among PRODUCT_MASTER's Phase 3 deliverables?",
         "Is Gerber export absent from PRODUCT_MASTER's Phase 3 deliverables list?", False,
         "- Gerber export + JLCPCB/PCBWay API integration")
polarity("p08_router", "S18", "Does PCB_STRATEGY recommend that Circuit OS build its own router rather than consume one?",
         "Does PCB_STRATEGY recommend that Circuit OS consume a router rather than build its own?", False,
         "The router is a commodity you should")
polarity("p09_led_decider", "S26", "Was the 2026-09-23 LED option decided by the agent rather than by a person?",
         "Was the 2026-09-23 LED option decided by a person rather than by the agent?", True,
         "so the agent\ndecided, taking the reversible option")
polarity("p10_protocol", "S28", "Does the earlier research report recommend keeping the >0.9 / 0.5–0.9 / <0.5 protocol as written?",
         "Does the earlier research report recommend replacing the >0.9 / 0.5–0.9 / <0.5 protocol?", False,
         "Do not keep the current >0.9 / 0.5–0.9 / <0.5 protocol as written.")
polarity("p11_blind", "S30", "In the first live Jev run, did every blind control fall to need_more_information?",
         "In the first live Jev run, did at least one blind control pick a substantive option instead of need_more_information?",
         True, "Every blind control fell to `need_more_information`")
polarity("p12_kind_code", "S25", "Is `kind` currently `analytic` for exact closed-form and proved claims in the code?",
         "Is `kind` currently `empirical` for exact closed-form and proved claims in the code?", True,
         "**`kind` for exact closed-form claims is `analytic`.**")

# ============================================================ B. owner decisions — the first run's questions, verbatim
PRIOR_REQS = [("rs485", "rs485_de_re_pulldown.json"), ("x7", "x7_live_pricing.json"), ("d1", "d1_bench_timing.json"),
              ("kind", "proof_kind_label.json"), ("explainer", "explainer_budget.json"),
              ("stage6", "stage6_finish.json"), ("flake", "accuracy_flake_policy.json"),
              ("bump", "pin_support_version_policy.json")]
for slug, fname in PRIOR_REQS:
    req = json.loads((REQ / fname).read_text(encoding="utf-8"))
    gov = req["governing"] if isinstance(req["governing"], list) else [req["governing"]]
    prior = req.get("agent_prior_agrees_with") or {}
    for qname, q in req["questions"].items():
        Q.append({"key": f"prior__{slug}__{qname}", "chunk": "B", "category": "owner_decision_prior_run",
                  "type": q["type"], "q": q, "source_request": fname, "governing": qname in gov,
                  "prior": prior.get(qname) if isinstance(prior, dict) else None,
                  "owner_owned": req.get("owner_owned"), "door": req.get("door")})

# ============================================================ B. owner decisions not run before
choice("od_d7_when", "B", "owner_decision",
       "When should the D7 datasheet verification pass (a person opening each datasheet behind the 155 figure records) happen?",
       {"before_stage6_commit": "Choose when Stage 6 substitution relies on unverified figures and should wait for them.",
        "interleave_one_family_per_session": "Choose when the work is best spread across sessions, one part family at a time.",
        "after_stage6": "Choose when Stage 6 does not depend on verification and the pass can follow it."},
       prior="interleave_one_family_per_session")
choice("od_d7_order", "B", "owner_decision",
       "In what order should the D7 verification pass take the figure records?",
       {"critical_claim_tiers_first": "Choose when figures that gate a critical claim should go first, stated assumptions and typical values before guaranteed ones, then the smallest audit margin.",
        "by_part_family": "Choose when grouping by part family (resistors, capacitors, MCUs, transceivers) matters most.",
        "by_generator": "Choose when finishing one generator's figures at a time matters most.",
        "by_record_id": "Choose when order does not matter and records can go in ID order."},
       prior="critical_claim_tiers_first")
choice("od_phase3_order", "B", "owner_decision", "Which Phase 3 programme should start first?",
       {"constraints_first": "Choose when the constraint layer + freerouting needs no customers and is the stated moat.",
        "industrial_first": "Choose when customer evidence makes a specific industrial generator class urgent.",
        "parallel": "Choose when one engineer can sustain both without either stalling.",
        NMI: "Choose when customer evidence (PCB_STRATEGY §9.3) is missing and would change the answer."},
       prior="constraints_first")
choice("od_gerber_resolution", "B", "owner_decision",
       "How should the contradiction between the Phase 3 KPI (prompt-to-ordered-PCB within one business day) and Gerber/fab APIs being Phase 4 be resolved?",
       {"move_minimal_gerber_into_phase3": "Choose when ordering a PCB in Phase 3 needs Gerber export, so a minimal version moves forward.",
        "restate_kpi_as_routed_kicad_board_handed_to_fab_by_user": "Choose when the KPI should be reworded so the user exports and orders from a routed KiCad board.",
        "keep_roadmap_as_written": "Choose when the contradiction does not matter enough to change either document."},
       prior="restate_kpi_as_routed_kicad_board_handed_to_fab_by_user")
noul("od_gerber_kpi_reachable", "B", "owner_decision",
     "As the Phase 3 KPI is now worded, is it reachable in Phase 3 without Gerber export?")
choice("od_phase2_governing_list", "B", "owner_decision",
       "Which deliverable list should govern whether Phase 2 is finished?",
       {"product_master_phase2_list": "Choose when PRODUCT_MASTER's Phase 2 deliverables (free-form, live pricing, RAG, version history UI, waveform viewer, substitution) must all be delivered.",
        "as_built_stages_0_to_6_under_v2": "Choose when PHASE_2_PLAN_v2's Stages 0–6 govern, as its higher precedence says.",
        "write_new_exit_gate_merging_both": "Choose when neither list alone is right and a written exit gate must be drafted first."},
       prior="as_built_stages_0_to_6_under_v2")
choice("od_standard_family", "B", "owner_decision",
       "For a Phase 3 DCV controller board, which standard family should a person review first?",
       {"ul_60730": "Automatic electrical controls for household and similar use (UL 60730-1).",
        "ul_61010_2_201": "Programmable controllers (UL 61010-1 / 61010-2-201).",
        "ul_508a_panel_only": "UL 508A, because the board is a component of an industrial control panel.",
        "none_apparent": "No listed family applies.",
        NMI: "Choose when the product's use and installation are unclear."},
       prior="ul_60730")
noul("od_hood_life_safety", "B", "owner_decision",
     "Could a failure of the commercial kitchen hood controller board plausibly affect life safety?")
choice("od_crit12_timing", "B", "owner_decision", "When should the criterion-12 external cold read be run?",
       {"now_before_any_phase3_outreach": "Choose when Phase 3 brings prospects soon, so the review should happen before any outreach.",
        "wait_for_trigger_first_external_user": "Choose when the recorded trigger (before the first external user sees an explanation) is enough on its own.",
        "after_first_enterprise_contract": "Choose when the review matters only once a contract exists."},
       prior="now_before_any_phase3_outreach")
noul("od_prospect_sees_explanation", "B", "owner_decision",
     "Will a prospect see a generated explanation within the first Phase 3 milestone?")
choice("od_raw_prompt_storage", "B", "owner_decision",
       "Should Circuit OS store raw prompt text so that a transcription-fidelity check (R1) can run on live traffic?",
       {"store_with_retention_limit": "Choose when live-traffic checking is worth storing prompts for all users with a retention limit.",
        "store_only_for_opt_in_users": "Choose when prompts should be stored only for users who opt in.",
        "keep_hash_only_use_seeded_corpus": "Choose when only the hash is kept and R1 is evaluated on a seeded prompt corpus instead."},
       prior="keep_hash_only_use_seeded_corpus")
choice("od_commit_convention", "B", "owner_decision", "Which commit-message convention should the project enforce?",
       {"conventional_everywhere": "Choose when every commit uses conventional-commit prefixes (feat, fix, test, …).",
        "session_prefix_for_worker_commits": "Choose when worker sessions commit as 'session: <description>' as AGENTS.md says.",
        "conventional_for_code_brain_for_memory": "Choose when code commits are conventional and memory commits use 'brain:'."},
       prior="conventional_for_code_brain_for_memory")

# ============================================================ B. Phase 2 exit readiness
DEF_TEXT = {s["id"]: None for s in SECS}
REG = {"D1": "predict() is validated against mathematics and ngspice, not hardware",
       "D2": "the MCU is represented by simplified electrical models, not the device",
       "D3": "no external engineer has read a generated explanation cold",
       "D4": "coverage growth cost may outrun one engineer",
       "D5": "an LLM may write the IntentIR, so the specification is untrusted",
       "D6": "block proofs may not compose into board claims",
       "D7": "datasheet parameters feeding predict() and the rule tables are unverified",
       "D8": "pi is irrational, so a z3 encoding of f_c must bracket it",
       "D9": "a generator bug makes predict() confidently wrong and nothing catches it"}
REF_EXIT = {"D6": ("already_closed_or_not_applicable", "register status not_yet_applicable (S10)"),
            "D8": ("already_closed_or_not_applicable", "register status eliminated (S10)")}
PRIOR_EXIT = {"D1": "acceptable_open_with_trigger", "D2": "acceptable_open_with_trigger",
              "D3": "acceptable_open_with_trigger", "D4": "acceptable_open_with_trigger",
              "D5": "acceptable_open_with_trigger", "D6": "already_closed_or_not_applicable",
              "D7": "acceptable_open_with_trigger", "D8": "already_closed_or_not_applicable",
              "D9": "acceptable_open_with_trigger"}
for d, text in REG.items():
    ref = REF_EXIT.get(d)
    choice(f"exit_{d}", "B", "phase2_exit_defeater",
           f"How should defeater {d} ({text}) stand when Phase 2 exits?",
           {"acceptable_open_with_trigger": "Choose when Phase 2 can exit with it still open, provided its trigger is recorded.",
            "must_close_before_exit": "Choose when Phase 2 should not exit while it is open.",
            "already_closed_or_not_applicable": "Choose when the register shows it eliminated or not yet applicable.",
            NMI: "Choose when the exit criteria needed to judge this are not in the state."},
           ref=ref[0] if ref else None, ref_derivation=ref[1] if ref else None, prior=PRIOR_EXIT[d])
STAGE_LEVELS = ["Not started", "In progress: gates not yet met or the work is uncommitted",
                "Gates met, with items recorded as not done", "Done: gates met and nothing material outstanding"]
STAGES = {"0": "instrumentation, harness, contract", "1": "IntentIR, registry, form, hard abstention",
          "2": "patch model v2", "3": "generator library, claims, grade floor", "4": "proof compiler and sign-off",
          "5": "multi-MCU firmware", "6": "BOM and substitution"}
for n, name in STAGES.items():
    score(f"exit_stage{n}", "B", "phase2_exit_stage", f"How ready is Phase 2 Stage {n} ({name}) for Phase 2 exit?",
          STAGE_LEVELS, ref=1 if n == "6" else None,
          ref_derivation="HANDOFF §8: Stage 6 in progress, uncommitted (S13)" if n == "6" else None)

# ============================================================ B. one-way vs two-way doors
DOOR = {"one_way_door": "Choose when the change alters signed or stored data, hashes, the public API, a generator's accepted set, fab cost or safety, so undoing it is costly or impossible.",
        "two_way_door": "Choose when the change can be undone cheaply and nothing signed, stored, public or safety-related is affected.",
        NMI: "Choose when the state lacks what is needed to tell."}
DOORS = [
    ("rs485_pulldown_default", "Adding the 10 kΩ DE/RE pull-down to every new rs485_node design, with a version bump.", "one_way_door", "version bump makes signed RS-485 designs return 409 (S21 D-1)"),
    ("rs485_pulldown_opt_in", "Adding the DE/RE pull-down as an opt-in constraint that defaults to false.", "two_way_door", "existing designs byte-identical; no signature impact (S21 D-1)"),
    ("bump_versions_stage6", "Bumping generator VERSION strings after the Stage 6 pin-support change.", "one_way_door", "signed designs return 409; un-bumping after signatures is not possible (S21 D-7)"),
    ("no_bump_stage6", "Leaving generator VERSION strings unchanged after the Stage 6 pin-support change.", "two_way_door", "a later bump stays possible (S21 D-7)"),
    ("kind_to_empirical", "Changing `kind` on exact proofs from analytic to empirical.", "two_way_door", "kind is not in the sign-off hash; flip back (S21 D-5); contestable because it changes serialized CircuitIR"),
    ("live_pricing_flag", "Enabling live pricing behind a flag.", None, "contestable: flag can be turned off, but adds a vendor secret/ToS dependency"),
    ("explanation_async", "Moving the LLM explanation off the request path, run asynchronously like simulation.", None, "contestable: reversible in code, but changes the API response flow"),
    ("raise_max_tokens", "Raising the explainer's max_tokens from 8192 to 16384.", "two_way_door", "a setting that can be lowered again (S21 D-6)"),
    ("store_raw_prompts", "Starting to store raw user prompt text.", "one_way_door", "stored data about users; what was collected cannot be un-collected"),
    ("xfail_flaky", "Marking the flaky accuracy test xfail(strict) with a tracked issue.", "two_way_door", "remove the marker (S21 D-9)"),
    ("change_circuit_id_namespace", "Changing CIRCUIT_ID_NAMESPACE, from which every circuit_id derives.", "one_way_door", "changes every design's circuit_id and orphans stored records (realize.py; S08 item 3)"),
    ("freerouting_not_astar", "Choosing to integrate freerouting in Phase 3 instead of extending the custom A* router.", "two_way_door", "a plan choice; nothing signed or stored changes"),
    ("regenerate_bench_d1", "Regenerating the BENCH_D1 sheet with current generator versions.", "two_way_door", "a document; regenerate again"),
    ("register_stage6_modules", "Registering the Stage 6 modules in regen_state.py and progress_gen.py.", "two_way_door", "tracker registration can be edited"),
    ("assert_ul508a_compliance", "Asserting UL 508A compliance for generated Phase 3 boards.", "one_way_door", "safety and liability claim (S21 D-13)"),
    ("sign_property_set", "A user signing a design's property set.", "one_way_door", "signed data is frozen; edits drop the signature (S11)"),
]
for slug, text, ref, why in DOORS:
    choice(f"door_{slug}", "B", "door", f"Is this pending change a one-way or a two-way door? Change: {text}", DOOR,
           ref=ref, ref_derivation=why, prior=ref)

# ============================================================ B. Phase 3 strategy
CLASSES = {"dcv": "Demand-controlled ventilation (DCV) board", "hood": "Commercial kitchen hood controller",
           "refrigeration": "Advanced refrigeration control", "rs485_io_opto": "RS-485 industrial I/O with optoisolation",
           "plc_style": "PLC-style control board (24 VDC inputs, relay outputs, 4–20 mA, Modbus slave)"}
choice("p3_first_class", "B", "phase3",
       "Which industrial class should be the first Phase 3 generator?",
       {"rs485_io_opto": "RS-485 industrial I/O with optoisolation.", "dcv": "The DCV board.",
        "hood": "The commercial kitchen hood controller.", "refrigeration": "Advanced refrigeration control.",
        "plc_style": "A PLC-style control board."}, prior="rs485_io_opto")
FIT = ["Needs machinery Circuit OS lacks (transients, switching)", "Mostly new proofs and rules",
       "Reuses some proofs and rules", "Reuses most proofs, rules and the RS-485 library"]
for slug, name in CLASSES.items():
    score(f"p3_fit_{slug}", "B", "phase3", f"How well does this class fit as the first Phase 3 generator? Class: {name}.", FIT)
    noul(f"p3_needs_switching_{slug}", "B", "phase3",
         f"Would generating this class require a switching converter or transient simulation, which Phase 2 does not have? Class: {name}.",
         ref=True if slug == "dcv" else None,
         ref_derivation="DCV needs a 24VAC-to-3.3V supply (S17; S28 finding 14)" if slug == "dcv" else None)
noul("p3_constraints_need_customers", "B", "phase3",
     "Does building the constraint layer with freerouting integration require customer evidence first?",
     ref=False, ref_derivation="S21 D-10: programme (A) 'needs no customers'")

# ============================================================ B. product / market
noul("pm_crit12_before_prospects", "B", "product_market",
     "Should the criterion-12 external cold read happen before any demo to a prospect?")
HYP = {"h1": "layout quality is the actual buying trigger, so constraints are a consolation prize",
       "h2": "Quilter or Flux ships intent-aware constraints and the moat closes",
       "h3": "HVAC customers want finished boards, not designs",
       "h4": "the constraint layer is harder than it looks and the constraints come out vague",
       "h5": "semantic placement rules do not generalise past the five templates"}
IMPACT = ["No change", "A minor adjustment", "Reorders Phase 3 priorities", "Invalidates the constraint-layer bet"]
for h, text in HYP.items():
    noul(f"pm_{h}_evidence_recorded", "B", "product_market",
         f"Does the state record any test or evidence that settles this PCB_STRATEGY §9 risk: {text}?",
         ref=False, ref_derivation="no test or evidence for any §9 hypothesis is recorded in the dossier (S18)")
    score(f"pm_{h}_impact", "B", "product_market",
          f"If this PCB_STRATEGY §9 risk turned out true, how much would it change Circuit OS's Phase 3 plan? Risk: {text}.", IMPACT)
choice("pm_audience_first", "B", "product_market", "Which audience should Phase 3 work serve first?",
       {"hobbyists": "Hobbyists.", "pcb_designers": "Professional PCB designers.", "hvac_controls": "HVAC and controls companies."},
       prior="hvac_controls")

# ============================================================ C. risk per subsystem
RISK = ["Negligible: well tested and nothing open", "Low", "Moderate", "High",
        "Critical: an open doubt could mislead users or block the roadmap"]
SUBSYSTEMS = {
    "intent_producer": "the LLM producer (prompt -> IntentIR, one tool_use call)",
    "form_producer": "the form producer (form -> IntentIR, zero calls)",
    "intent_patcher": "the LLM patcher (command -> RFC 6902 ops over IntentIR)",
    "registry_dispatch": "registry dispatch by envelope()",
    "realize_stamping": "realize(): generate, stamp circuit_id/version/generator, locality, predict() delta",
    "rc_lowpass": "the rc_lowpass generator", "voltage_divider": "the voltage_divider generator",
    "led_indicator": "the led_indicator generator", "dht22_node": "the dht22_node generator",
    "rs485_node": "the rs485_node generator",
    "spice_ngspice": "the SPICE netlist generator with ngspice via Celery and the grader",
    "firmware_compile_gate": "firmware generation with the PlatformIO compile gate",
    "kicad_schematic": "the KiCad schematic generator",
    "bom_substitution": "the BOM compiler and Stage 6 substitution",
    "llm_explainer": "the LLM explainer", "derived_explainer": "the derived (zero-call) explainer",
    "claims_coverage": "claims and validation_coverage (grades, verdicts, grade_floor)",
    "proof_compiler": "the proof compiler (sympy + z3, sign-off, frozen refine loop)",
    "pin_rules": "the pin rules (pin-mux, peripheral conflict, strapping pins)",
    "defeater_register": "the defeater register D1–D9",
    "auth_persistence": "auth (JWT), rate limiting and PostgreSQL persistence",
    "pcb_engine": "the experimental PCB engine (custom A* router)",
    "ci_pipeline": "the CI pipeline",
}
for slug, name in SUBSYSTEMS.items():
    score(f"risk_{slug}", "C", "risk", f"How much risk does {name} carry for Circuit OS right now?", RISK)

# ============================================================ C. priority per candidate next move
PRIO = ["Do not do", "Later (Phase 3 or beyond)", "Soon (after the current work)", "Next (this month)",
        "Now (before anything else)"]
MOVES = {
    "finish_commit_stage6": "Finish, register and commit the Stage 6 BOM + substitution work",
    "ci_on_phase2_branch": "Make CI run on the phase2-stage0 branch with PlatformIO",
    "scanner_new_clients": "Close the One-Rule scanner hole for new model clients (e.g. a TypeSafe client)",
    "register_modules": "Register the unregistered backend modules in the trackers",
    "regenerate_bench_d1": "Regenerate the stale BENCH_D1 sheet",
    "d1_evidence_records": "Build the D1 evidence-record code",
    "d7_verification_pass": "Run the D7 datasheet verification pass",
    "crit12_cold_read": "Run the criterion-12 external cold read",
    "rs485_pulldown": "Add the RS-485 DE/RE pull-down",
    "live_pricing": "Enable live component pricing (X7)",
    "explanation_async": "Move the LLM explanation off the request path",
    "diagnose_flaky": "Diagnose the flaky accuracy test with seed-logged repeat runs",
    "judgment_record": "Build a Judgment record and jev_judgment table for Jev outputs",
    "r1_shadow": "Run a transcription-fidelity check (R1) in shadow mode",
    "r2_shadow": "Run a patch-op faithfulness check (R2) in shadow mode",
    "constraint_rule_table": "Build the ConstraintRule table and the L1–L4 layout defeaters",
    "freerouting": "Integrate freerouting",
    "first_industrial_generator": "Author the first industrial generator",
    "gerber_kpi": "Resolve the Gerber / Phase 3 KPI contradiction",
    "phase2_exit_gate": "Write a Phase 2 exit gate",
    "g0_proof_checker": "Build a G0 proof checker (independent certificate check)",
    "transient_sim": "Add transient simulation",
    "flash_a_board": "Flash a board and run the generated firmware",
    "design_route_coverage": "Raise test coverage of the design route",
}
for slug, name in MOVES.items():
    score(f"prio_{slug}", "C", "priority", f"What priority should this candidate next move have? Move: {name}.", PRIO)

# ============================================================ C. Jev's self-assessment of the 33 proposed uses
SUIT = ["Unsuitable: needs computation, text generation or a guarantee Jev cannot give",
        "Marginal: only as an offline hint a person always reviews",
        "Suitable with guardrails: advisory or shadow, never deciding alone",
        "Well suited: a narrow typed judgment Jev can make directly"]
USES = {
    "R1": ("Transcription fidelity: per requested value, is it stated in the user's prompt, and which catalogue function does the prompt ask for; stable low probability returns a confirm question instead of accepting.", 2),
    "R2": ("Patch-op faithfulness: do the cited command words ask for this operation; doubt refuses the patch and keeps v(n).", 2),
    "R3": ("X5 retry-added fields: is a value added by the retry stated in the prompt; low probability marks the field underdetermined.", 2),
    "R4": ("Sign-off doubt hints: highlight requirement fields for the user to check before signing; negative-only, never a 'Jev agrees' badge.", 2),
    "R5": ("Catalogue-function disagreement: log when the function the prompt asks for differs from the LLM's IntentIR function.", 3),
    "R6": ("Extra underdetermined questions: may add a question about a required field, never remove one.", 2),
    "R7": ("Refusal backlog labelling: label refused requests with owner-defined Phase 3 categories to order the backlog.", 3),
    "R8": ("D7 figure triage: score datasheet figures to break ties in the verification queue order.", 1),
    "R9": ("D3 explanation pre-screen: rubric score of generated explanations as a regression metric; never counts for criterion 12.", 1),
    "R10": ("D9 mutation-target ideas: which component fault would the 2% grid gate be least sensitive to, to become a seeded-fault test.", 0),
    "R11": ("Substitute ordering: sort already-surfaced substitute parts by the user's stated preference; never surfaces or filters.", 2),
    "P1": ("net_role: label the role of a generic net in new industrial generators (0–10 V output, 4–20 mA loop, relay coil, 24 V input); the generator's declared role wins.", 2),
    "P2": ("env_label: label pollution degree, overvoltage category and indoor vs field-wired from the user's description; the stricter label is used until the user confirms.", 2),
    "P3": ("isolation_needed: judge whether ground-potential difference could exceed the RS-485 common-mode range; short of a stable confirmed 'no', the isolated design is used.", 1),
    "P4": ("Standard-family triage: flag which standard family a person should review (60730, 61010-2-201, 508A panel, none) and 'possibly life-safety'; a person decides.", 2),
    "P5": ("component_role: role label for a library part without a declared role; the fallback is flagged.", 2),
    "P6": ("DRC waiver triage: cosmetic, needs_review or safety_relevant to order the review queue; every waiver is signed by a person.", 2),
    "P7": ("Private-library admission triage: accept, needs_datasheet_check or reject, after deterministic checks pass.", 2),
    "P8": ("'Is 4-layer justified?' after 2-layer layouts fail: never auto-upgrades; a person confirms.", 1),
    "T1": ("entry_covers_diff: advisory PR comment on whether the new decisions.md entry covers the diff.", 2),
    "T2": ("failure_class: classify test tracebacks the deterministic classifier cannot match; a retry only for a stable infra hiccup outside accuracy tests.", 3),
    "T3": ("contradicts_derived_fact: flag prose paragraphs that contradict state.json excerpts, as a to-fix list for a human.", 2),
    "T4": ("needs_owner_attention: a PR label, never an approval.", 2),
    "O1": ("RS-485 DE/RE pull-down: a recommendation to the owner, who decides.", 1),
    "O2": ("X7 live pricing: a recommendation to the owner; the default stays static.", 1),
    "O3": ("D1 bench timing: a recommendation to the owner.", 1),
    "O4": ("D7 verification order: deterministic tiers first, Jev only breaks ties.", 1),
    "O5": ("`kind` on exact proofs: a recommendation to the owner.", 1),
    "O6": ("Explainer budget next step: a recommendation to the owner.", 1),
    "O7": ("Stage 6 version bumps, residual case after a deterministic byte-compare.", 1),
    "O8": ("Stage 6 status and 5% KPI disposition: reversible scheduling by the agent with care.", 2),
    "O9": ("Flaky accuracy test policy: the agent acts with care.", 2),
    "O10": ("Phase 3 scope order: a recommendation to the owner.", 1),
}
for uid, (desc, prior) in USES.items():
    score(f"self_{uid}", "C", "self_assessment",
          {"proposed_use": f"{uid} — {desc}",
           "question": "How suitable is Jev (a model that returns calibrated probabilities for typed questions but cannot compute, generate text or verify) for this proposed use in Circuit OS?"},
          SUIT, prior=prior)


def main():
    keys = [q["key"] for q in Q]
    assert len(keys) == len(set(keys)), "duplicate keys"
    for q in Q:
        if q["type"] == "choice":
            assert NMI in q["q"]["criteria"], q["key"]
    battery = {"built": "2026-09-24", "model": "jev-1.13.0",
               "dossier_sha256": hashlib.sha256(FULL.encode()).hexdigest(),
               "core_sha256": hashlib.sha256(CORE.encode()).hexdigest(),
               "n_questions": len(Q), "questions": Q}
    (HERE / "battery.json").write_text(json.dumps(battery, indent=1, ensure_ascii=False), encoding="utf-8")
    labelled = [{k: q.get(k) for k in ("key", "category", "sub", "type", "gt", "gt_derivation", "ref",
                                       "ref_derivation", "prior", "section", "anchor", "anchor_hits", "multi",
                                       "in_core", "world_knowledge", "pair")}
                for q in Q if q.get("gt") is not None or q.get("ref") is not None or q.get("prior") is not None]
    prereg = {"prepared": "2026-09-24, before any battery call",
              "scoring_rules": {
                  "needle_present_choice": "correct iff argmax == gt",
                  "needle_absent_choice": "correct iff argmax == need_more_information",
                  "needle_absent_noul": "abstain-like iff 0.25 <= p_yes <= 0.75; confidently wrong iff p<0.1 or p>0.9",
                  "polarity_noul": "correct iff (p_yes > 0.5) == gt; pair coherent iff |p_pos + p_neg - 1| <= 0.15",
                  "position": "tercile of the first anchor occurrence's relative offset in the layout sent",
                  "core_variant": "needles whose anchor is absent from the core dossier are scored against need_more_information / abstain-like",
                  "reference_labels": "door/exit/phase3/product refs derived from dossier text or the report's door definition; not Jev",
                  "priors": "agent's own analysis written before the call; used only for band agreement"},
              "dossier_sha256": battery["dossier_sha256"], "core_sha256": battery["core_sha256"],
              "labels": labelled}
    (HERE / "prereg_labels.json").write_text(json.dumps(prereg, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("questions:", len(Q), Counter(q["chunk"] for q in Q), Counter(q["category"] for q in Q))
    print("needles present:", sum(q.get("sub") == "present" for q in Q), "absent:", sum(q.get("sub") in ("absent", "absent_noul") for q in Q),
          "polarity pairs:", len({q['pair'] for q in Q if q.get('pair')}))
    print("present needles in core:", sum(q.get("sub") == "present" and q["in_core"] for q in Q),
          "multi-occurrence:", sum(bool(q.get("multi")) for q in Q if q.get("sub") == "present"))
    for f in ("battery.json", "prereg_labels.json"):
        print(f, hashlib.sha256((HERE / f).read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
