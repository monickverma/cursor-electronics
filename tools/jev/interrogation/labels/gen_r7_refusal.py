"""R7 / B13 — refusal-backlog labelling over synthetic refused requests.

Each row is what `observability/request_log.py` keeps for a refusal: the IntentIR requirements the producer
wrote and the dispatcher's `refusal_summary()` — computed here by running the real registry of the code
snapshot (e803a99) on the requirements, so the refusal text is the product's own. Today only a prompt hash
is stored, so the primary arm shows no prompt; a second arm adds the raw prompt to measure what storing it
would buy. Labels by construction (the request was written to need exactly that label).
"""
import sys
from collections import Counter

from common import SNAPSHOT, cite, pick_subset, write_set

QUESTIONS = {
    "refusal_label": {  # B13 verbatim
        "type": "choice",
        "instructions": "What does this refused request most need from Circuit OS?",
        "criteria": {
            "range_widen_existing": "An existing function refused on range; widen an envelope.",
            "high_pass_filter": "A new high-pass filter generator.",
            "band_pass_filter": "A new band-pass generator.",
            "op_amp_stage": "An op-amp stage.",
            "industrial_io": "24 V inputs, 4-20 mA, 0-10 V or relay I/O.",
            "out_of_scope": "Switching converters, PCB-only or free-form requests.",
            "ambiguous_request": "The request is unclear.",
            "none_of_these": "None of the above; a human should extend the label set.",
        },
    }
}


def R(function, targets=None, constraints=None, preferences=None):
    return {"function": function, "targets": targets or {}, "constraints": constraints or {}, "preferences": preferences or {}}


# (id, truth, prompt, requirements, contestable)
ITEMS = [
    ("W01", "range_widen_existing", "RC low-pass filter with a 2 MHz cutoff on a 5 V signal.", R("low_pass_filter", {"cutoff_hz": 2e6}, {"supply_v": 5.0}), False),
    ("W02", "range_widen_existing", "Low-pass filter at 20 Hz to smooth a slow 3.3 V sensor signal.", R("low_pass_filter", {"cutoff_hz": 20.0}, {"supply_v": 3.3}), False),
    ("W03", "range_widen_existing", "Divide 48 V down to 3 V for my ADC.", R("voltage_divider", {"vout_v": 3.0}, {"supply_v": 48.0}), False),
    ("W04", "range_widen_existing", "Voltage divider giving 5 V from 12 V.", R("voltage_divider", {"vout_v": 5.0}, {"supply_v": 12.0}), False),
    ("W05", "range_widen_existing", "Indicator LED at 30 mA from an Arduino Uno pin.", R("led_indicator", {"led_current_ma": 30.0}, {"supply_v": 5.0, "mcu": "arduino_uno"}), False),
    ("W06", "range_widen_existing", "A 20 mA indicator LED on an ESP32 DevKitC.", R("led_indicator", {"led_current_ma": 20.0}, {"supply_v": 3.3, "mcu": "esp32_devkitc"}), False),
    ("W07", "range_widen_existing", "DHT22 temperature sensor on a 40 m cable to an Uno.", R("temperature_humidity_sensor", {}, {"cable_length_m": 40.0, "supply_v": 5.0, "mcu": "arduino_uno"}), False),
    ("W08", "range_widen_existing", "Modbus RTU master at 115200 baud on an Arduino Uno.", R("modbus_rtu_master", {}, {"supply_v": 5.0, "baud": 115200, "mcu": "arduino_uno"}), False),
    ("W09", "range_widen_existing", "RS-485 Modbus master board powered at 12 V.", R("modbus_rtu_master", {}, {"supply_v": 12.0}), False),
    ("W10", "range_widen_existing", "A 0.4 V reference from a 5 V rail using a resistor divider.", R("voltage_divider", {"vout_v": 0.4}, {"supply_v": 5.0}), False),
    ("H01", "high_pass_filter", "RC high-pass at 50 Hz to block DC from a sensor.", R("high_pass_filter", {"cutoff_hz": 50.0}), False),
    ("H02", "high_pass_filter", "AC coupling network with a 20 Hz corner for an audio input.", R("ac_coupling_filter", {"cutoff_hz": 20.0}), False),
    ("H03", "high_pass_filter", "High-pass filter at 0.1 Hz to remove accelerometer drift.", R("high_pass_filter", {"cutoff_hz": 0.1}), False),
    ("H04", "high_pass_filter", "Passive CR high-pass with a 1 kHz corner, 5 V signal.", R("rc_high_pass", {"cutoff_hz": 1000.0}, {"supply_v": 5.0}), False),
    ("H05", "high_pass_filter", "Strip the DC offset from a photodiode signal before the ADC: 5 Hz high-pass.", R("high_pass_filter", {"cutoff_hz": 5.0}), False),
    ("H06", "high_pass_filter", "First-order high-pass at 300 Hz for a microphone.", R("high_pass_filter", {"cutoff_hz": 300.0}), False),
    ("H07", "high_pass_filter", "A high-pass filter that removes everything below 10 kHz.", R("high_pass_filter", {"cutoff_hz": 10000.0}), False),
    ("B01", "band_pass_filter", "Band-pass from 300 Hz to 3.4 kHz for a voice channel.", R("band_pass_filter", {"low_cutoff_hz": 300.0, "high_cutoff_hz": 3400.0}), False),
    ("B02", "band_pass_filter", "Bandpass around 40 kHz for an ultrasonic receiver.", R("band_pass_filter", {"center_hz": 40000.0}), False),
    ("B03", "band_pass_filter", "RC band-pass that passes 1 kHz to 10 kHz.", R("rc_band_pass", {"low_cutoff_hz": 1000.0, "high_cutoff_hz": 10000.0}), False),
    ("B04", "band_pass_filter", "A filter that passes only 18 to 22 kHz.", R("band_pass_filter", {"low_cutoff_hz": 18000.0, "high_cutoff_hz": 22000.0}), False),
    ("B05", "band_pass_filter", "Band-pass for a heart-rate sensor, 0.5 to 5 Hz.", R("band_pass_filter", {"low_cutoff_hz": 0.5, "high_cutoff_hz": 5.0}), False),
    ("B06", "band_pass_filter", "Passband from 100 Hz to 1 kHz on a 5 V signal.", R("bandpass_filter", {"low_cutoff_hz": 100.0, "high_cutoff_hz": 1000.0}, {"supply_v": 5.0}), False),
    ("B07", "band_pass_filter", "Band-pass centred at 1 kHz.", R("band_pass_filter", {"center_hz": 1000.0}), False),
    ("O01", "op_amp_stage", "Microphone preamp with a gain of 100 using an op-amp.", R("op_amp_amplifier", {"gain": 100.0}), False),
    ("O02", "op_amp_stage", "Unity-gain op-amp buffer after a voltage divider.", R("voltage_buffer", {"gain": 1.0}), False),
    ("O03", "op_amp_stage", "Inverting amplifier with a gain of -4.7.", R("inverting_amplifier", {"gain": -4.7}), False),
    ("O04", "op_amp_stage", "Transimpedance amplifier for a photodiode with a 1 Mohm feedback resistor.", R("transimpedance_amplifier", {"feedback_ohm": 1e6}), False),
    ("O05", "op_amp_stage", "Non-inverting amplifier, gain 11, for a 0-300 mV sensor into a 3.3 V ADC.", R("non_inverting_amplifier", {"gain": 11.0}, {"supply_v": 3.3}), False),
    ("O06", "op_amp_stage", "Summing amplifier that mixes two audio signals.", R("summing_amplifier", {"inputs": 2}), False),
    ("O07", "op_amp_stage", "Op-amp difference amplifier across a current shunt, gain 20.", R("difference_amplifier", {"gain": 20.0}), False),
    ("I01", "industrial_io", "4-20 mA input for a pressure transmitter into an Arduino.", R("current_loop_input", {"range_ma": [4, 20]}, {"mcu": "arduino_uno"}), False),
    ("I02", "industrial_io", "0-10 V output to drive a VFD speed input.", R("analog_output_0_10v", {"range_v": [0, 10]}), False),
    ("I03", "industrial_io", "24 V digital input with an optocoupler for a proximity sensor.", R("digital_input_24v", {"input_v": 24.0}), False),
    ("I04", "industrial_io", "Relay output to switch a 24 VAC damper actuator.", R("relay_output", {"load_v": 24.0}), False),
    ("I05", "industrial_io", "Read a 0-10 V humidity transmitter with an MCU.", R("analog_input_0_10v", {"range_v": [0, 10]}), False),
    ("I06", "industrial_io", "Eight-channel opto-isolated 24 V input board.", R("digital_input_24v", {"channels": 8, "input_v": 24.0}), False),
    ("I07", "industrial_io", "4-20 mA output to a valve positioner.", R("current_loop_output", {"range_ma": [4, 20]}), False),
    ("I08", "industrial_io", "Relay board to switch contactor coils from a microcontroller.", R("relay_output", {"channels": 4}), False),
    ("X01", "out_of_scope", "Buck converter from 24 V to 5 V at 2 A.", R("buck_converter", {"vout_v": 5.0, "iout_a": 2.0}, {"supply_v": 24.0}), False),
    ("X02", "out_of_scope", "Boost a 3.7 V Li-ion cell up to 12 V.", R("boost_converter", {"vout_v": 12.0}, {"supply_v": 3.7}), False),
    ("X03", "out_of_scope", "Flyback power supply from 230 VAC to 12 V.", R("flyback_converter", {"vout_v": 12.0}, {"supply_vac": 230.0}), False),
    ("X04", "out_of_scope", "Switch-mode regulator, 12 V to 3.3 V at 3 A.", R("switching_regulator", {"vout_v": 3.3, "iout_a": 3.0}, {"supply_v": 12.0}), False),
    ("X05", "out_of_scope", "Route my KiCad board and give me a two-layer layout.", R("pcb_layout", {"layers": 2}), False),
    ("X06", "out_of_scope", "Generate Gerber files for my existing PCB.", R("gerber_export", {}), False),
    ("X07", "out_of_scope", "Design a complete quadcopter flight controller.", R("flight_controller", {}), False),
    ("X08", "out_of_scope", "Build a smart-home hub with Zigbee, Wi-Fi and a touchscreen.", R("smart_home_hub", {}), False),
    ("X09", "out_of_scope", "Design an electric-skateboard motor controller (ESC).", R("motor_esc", {}), False),
    ("Q01", "ambiguous_request", "make my circuit better", R("unspecified"), False),
    ("Q02", "ambiguous_request", "something to control my garden", R("garden_control"), False),
    ("Q03", "ambiguous_request", "I need a sensor thing", R("sensor"), False),
    ("Q04", "ambiguous_request", "fix the noise", R("noise_fix"), False),
    ("Q05", "ambiguous_request", "a filter", R("filter"), False),
    ("Q06", "ambiguous_request", "circuit for my car", R("car_circuit"), False),
    ("Q07", "ambiguous_request", "do the usual one", R("unspecified"), False),
    ("Q08", "ambiguous_request", "the board we talked about yesterday", R("unspecified"), False),
    ("Z01", "none_of_these", "555 timer astable blinking an LED at 1 Hz.", R("astable_555", {"frequency_hz": 1.0}), False),
    ("Z02", "none_of_these", "H-bridge to drive a 12 V DC motor in both directions.", R("h_bridge_motor_driver", {"motor_v": 12.0}), False),
    ("Z03", "none_of_these", "Stepper motor driver with an A4988.", R("stepper_driver", {}), False),
    ("Z04", "none_of_these", "LiPo charger with a TP4056.", R("battery_charger", {"chemistry": "lipo"}), True),
    ("Z05", "none_of_these", "Capacitive touch button with a TTP223.", R("touch_sensor", {}), False),
    ("Z06", "none_of_these", "IR remote receiver (TSOP38238) on an Arduino.", R("ir_receiver", {}, {"mcu": "arduino_uno"}), False),
    ("Z07", "none_of_these", "Piezo buzzer driver.", R("buzzer_driver", {}), False),
    ("Z08", "none_of_these", "Hobby servo control on pin 9.", R("servo_control", {"pin": 9}), False),
]

PARAPHRASE_PROMPTS = {  # the prompt arm's paraphrase variant (requirements and refusal text unchanged)
    "W01": "Need a low-pass RC for a 5 V signal with the corner at 2 MHz.",
    "W05": "Drive an indicator LED at 30 mA straight off an Uno GPIO.",
    "H01": "Block the DC on a sensor line with an RC high-pass, corner 50 Hz.",
    "H05": "Before the ADC I want the photodiode's DC offset gone: high-pass around 5 Hz.",
    "B01": "Voice channel: keep 300 Hz to 3.4 kHz, reject the rest.",
    "O04": "Photodiode to voltage: a TIA with 1 Mohm in the feedback.",
    "I01": "Arduino needs to read a pressure transmitter's 4-20 mA signal.",
    "I04": "Switch a 24 VAC damper actuator with a relay output.",
    "X01": "24 V in, 5 V out at 2 A, switching buck please.",
    "Q05": "filter",
    "Z02": "Drive a 12 V DC motor forwards and backwards (H-bridge).",
    "Z08": "Control a hobby servo from pin 9.",
}


class _Intent:
    __slots__ = ("requirements",)

    def __init__(self, requirements):
        self.requirements = requirements


def refusal_summaries(reqs):
    sys.path.insert(0, str(SNAPSHOT / "backend"))
    from generators.registry import default_registry  # noqa: E402  (snapshot code, read-only)
    reg = default_registry()
    out = {}
    for iid, req in reqs.items():
        d = reg.dispatch(_Intent(req))
        if d.accepted:
            raise SystemExit(f"{iid}: the snapshot registry ACCEPTS this request ({d.generator.name}); fix the item")
        out[iid] = d.refusal_summary()
    return out


def main():
    summaries = refusal_summaries({iid: req for iid, _, _, req, _ in ITEMS})
    counts = Counter(req["function"] for _, _, _, req, _ in ITEMS)
    items = []
    for iid, truth, prompt, req, contestable in ITEMS:
        state = {"refusal_reason": summaries[iid], "intent_ir_requirements": req,
                 "rows_with_same_function_in_log": counts[req["function"]]}
        item = {"id": f"R7-{iid}", "state": state, "prompt_state": {**state, "prompt": prompt},
                "truth": {"refusal_label": truth}, "contestable": contestable,
                "derivation": f"Written as a request that needs '{truth}' (B13 definitions); refusal text from the snapshot registry."}
        if iid in PARAPHRASE_PROMPTS:
            item["paraphrase_state"] = {**state, "prompt": PARAPHRASE_PROMPTS[iid]}
        items.append(item)
    ids = [i["id"] for i in items]
    write_set("r7_refusal", {
        "task": "R7/B13 refusal-backlog labelling (Choice over owner-defined Phase 3 labels + none_of_these)",
        "questions": QUESTIONS,
        "truth_rule": "Each synthetic request is written to need exactly one B13 label; Z04 (TP4056 linear charger) is marked contestable (could be read as power electronics).",
        "arms": {"intent_only": "state = refusal_reason + intent_ir_requirements + group count (what request_log stores today)",
                 "with_prompt": "the same plus the raw prompt text (would need an owner decision to store prompts)"},
        "snapshot": "origin/phase2-stage0 at e803a99 (scratchpad copy); refusal_reason = GeneratorRegistry.dispatch(...).refusal_summary()",
        "citations": cite("TEMPLATE_B13"),
        "variants": {
            "repeat_subset": pick_subset(ids, 16, "r7_repeat"),
            "paraphrase_subset": sorted(i["id"] for i in items if "paraphrase_state" in i),
            "blind_subset": pick_subset(ids, 3, "r7_blind"),
        },
        "items": items,
    })


if __name__ == "__main__":
    main()
