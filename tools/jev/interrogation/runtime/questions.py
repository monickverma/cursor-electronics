"""State + question builders for every (corpus, item, variant). Pure functions, no network.

Original wording is the B11 / B12 templates of reports/Jev decisions for Circuit OS Phase 3.md
(tools/jev/templates/transcription_fidelity.questions.json, patch_op_faithful.questions.json),
with one necessary change: B11's function labels are generator names (rc_lowpass, dht22_node, ...)
but IntentIR.requirements.function holds catalogue function names, so the labels here are the
function names with B11's descriptions unchanged.

Transcription variants: O original | R choice labels reversed | P repeat (run sequentially, for
latency) | Q paraphrased prompt | E value also rendered with an SI prefix by code | S semantic
residue (numeric leaves left to the deterministic check; only non-numeric questions asked) |
D sharpened function/unrepresented wording | N negated polarity (subset).
Patch variants: O | P repeat | Q paraphrased command | V operations in reversed order | N negated.
Injection variants: O | P repeat.
"""
import json

from detcheck import UNITS, is_numeric_leaf

FUNCTION_B11 = {
    "low_pass_filter": "An RC low-pass filter.",
    "voltage_divider": "A resistive divider.",
    "led_indicator": "An LED with a current-limiting resistor.",
    "temperature_humidity_sensor": "A DHT22 temperature/humidity node.",
    "modbus_rtu_master": "An RS-485 Modbus node.",
    "none_of_these": "Anything else, including band-pass or high-pass.",
}
FUNCTION_SHARP = {
    "low_pass_filter": "A passive first-order RC low-pass filter: one resistor and one capacitor, passing frequencies below the cutoff. Not high-pass, band-pass, notch or active (op-amp) filters.",
    "voltage_divider": "A two-resistor divider that scales a DC voltage down to a lower DC voltage. Not a regulator or converter.",
    "led_indicator": "A single indicator LED driven from a microcontroller GPIO pin through one current-limiting resistor. Not LED strips or addressable LEDs.",
    "temperature_humidity_sensor": "A DHT22 (AM2302) temperature and humidity sensor wired to a microcontroller. Not other sensors such as DHT11, BME280 or SHT31.",
    "modbus_rtu_master": "A microcontroller acting as the Modbus RTU master on an RS-485 bus. Not a Modbus slave, Modbus TCP, CAN or other buses.",
    "none_of_these": "Anything else, including high-pass, band-pass, notch or active filters, power converters, other sensors, Modbus slaves and other buses.",
}
STATED_CRITERIA = {"true": "The words say it or leave no other reading.",
                   "false": "The value is absent, different in scale/unit, or belongs to another field."}
NOTSTATED_CRITERIA = {"true": "The prompt does not give this value for this field.",
                      "false": "The prompt states this value for this field or leaves no other reading."}
UNREP_B11 = {"type": "noul", "instructions": "Does the prompt ask for anything these requirements do not represent?"}
UNREP_SHARP = {"type": "noul", "instructions": "Does the prompt ask for anything these requirements do not represent?",
               "criteria": {"true": "The prompt asks for a function, part, value or feature that has no matching entry in the requirements.",
                            "false": "Every function, part, value and feature the prompt asks for has a matching entry in the requirements."}}
ALL_REPRESENTED = {"type": "noul", "instructions": "Is everything the prompt asks for represented in these requirements?"}
COVERED = {"type": "noul", "instructions": "Do these operations together make every change the command asks for, and nothing else?"}
NOT_COVERED = {"type": "noul", "instructions": "Does the command ask for any change these operations do not make, or do the operations make any change the command does not ask for?"}

T_VARIANTS = ("O", "R", "P", "Q", "E", "S", "D", "N")
P_VARIANTS = ("O", "P", "Q", "V", "N")
I_VARIANTS = ("O", "P")


def qname(prefix, path):
    return f"{prefix}__{path.replace('.', '__')}"


def leaves(r):
    out = {}
    for sec in ("targets", "constraints", "preferences"):
        for k, v in (r.get(sec) or {}).items():
            out[f"{sec}.{k}"] = v
    return out


def render(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _unit(path):
    u = UNITS.get(path, "")
    return f" {u}" if u else ""


_SI = {"Hz": ("Hz", 1.0), "V": ("V", 1.0), "mA": ("A", 1e-3), "m": ("m", 1.0), "ohm": ("ohm", 1.0), "ms": ("s", 1e-3)}
_PREFIX = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ")]


def eng(path, v):
    """SI-prefixed rendering computed in code, or None when it adds nothing."""
    unit = UNITS.get(path, "")
    if unit not in _SI or isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
        return None
    base, scale = _SI[unit]
    si = v * scale
    for mult, pre in _PREFIX:
        if abs(si) >= mult:
            mant = si / mult
            break
    else:
        mult, pre = 1e-6, "µ"
        mant = si / mult
    text = f"{mant:.4g} {pre}{base}"
    return None if text == f"{render(v)} {unit}" else text


def stated_q(path, v, with_eng=False):
    tail = ""
    if with_eng:
        e = eng(path, v)
        tail = f" (that is, {e})" if e else ""
    return {"type": "noul", "instructions": f"Does the prompt state or directly imply {path} = {render(v)}{_unit(path)}{tail}?",
            "criteria": dict(STATED_CRITERIA)}


def notstated_q(path, v):
    return {"type": "noul",
            "instructions": f"Is {path} = {render(v)}{_unit(path)} absent from the prompt, given there with a different value, scale or unit, or given for a different field?",
            "criteria": dict(NOTSTATED_CRITERIA)}


def function_q(table, reverse=False):
    items = list(table.items())
    if reverse:
        items.reverse()
    return {"type": "choice", "instructions": "Which catalogue function does the prompt ask for?", "criteria": dict(items)}


def t_state(prompt, requirements, corpus):
    return {"prompt": prompt, "requirements": requirements, "catalogue": corpus["state_catalogue"],
            "boards": corpus["state_boards"]}


def t_request(item, variant, corpus, prompt_override=None):
    """(state, questions) for a transcription (or transcription-injection) item."""
    prompt = prompt_override if prompt_override is not None else item["prompt"]
    if variant == "Q":
        prompt = item["prompt_paraphrase"]
    state = t_state(prompt, item["requirements"], corpus)
    lv = leaves(item["requirements"])
    qs = {}
    if variant == "N":
        for p, v in lv.items():
            qs[qname("notstated", p)] = notstated_q(p, v)
        qs["all_represented"] = dict(ALL_REPRESENTED)
        return state, qs
    for p, v in lv.items():
        if variant == "S" and is_numeric_leaf(v):
            continue
        qs[qname("stated", p)] = stated_q(p, v, with_eng=(variant == "E"))
    qs["function_asked"] = function_q(FUNCTION_SHARP if variant == "D" else FUNCTION_B11, reverse=(variant == "R"))
    qs["unrepresented_request"] = dict(UNREP_SHARP if variant == "D" else UNREP_B11)
    return state, qs


def op_q(command, o, negated=False):
    w, path = o["because"], o["path"]
    if o["op"] == "remove":
        if negated:
            text = f"In the command '{command}', do the cited words '{w}' ask for something other than removing {path} (a different change, or no change at all)?"
        else:
            text = f"In the command '{command}', do the cited words '{w}' ask to remove {path}?"
    else:
        v = json.dumps(o["value"], ensure_ascii=False)
        if negated:
            text = f"In the command '{command}', do the cited words '{w}' ask for something other than setting {path} to {v} (a different field, a different value, or no change at all)?"
        else:
            text = f"In the command '{command}', do the cited words '{w}' ask to set {path} to {v}?"
    return {"type": "noul", "instructions": text}


def p_request(item, variant, command_override=None):
    """(state, questions, op_order) for a patch (or patch-injection) item.

    op_order[k] is the index in item['operations'] of the operation asked about as op_<k>.
    """
    command = command_override if command_override is not None else item["command"]
    ops = item["operations"]
    if variant == "Q":
        command, ops = item["command_paraphrase"], item["operations_paraphrase"]
    order = list(range(len(ops)))
    if variant == "V":
        order.reverse()
    shown = [ops[i] for i in order]
    state = {"command": command, "current_requirements": item["current_requirements"], "operations": shown}
    qs = {}
    for k, o in enumerate(shown):
        qs[f"{'notop' if variant == 'N' else 'op'}_{k}"] = op_q(command, o, negated=(variant == "N"))
    qs["not_covered" if variant == "N" else "command_fully_covered"] = dict(NOT_COVERED if variant == "N" else COVERED)
    return state, qs, order


def n_subset(item_id):
    """Negated-polarity subset: items whose numeric suffix is odd (fixed before any call)."""
    return int(item_id.split("-")[1][1:]) % 2 == 1


def build_all(tc, pc, ic):
    """Every planned request: list of dicts with corpus, item_id, variant, state, questions, meta."""
    plan = []
    for it in tc["items"]:
        for v in T_VARIANTS:
            if v == "N" and not n_subset(it["id"]):
                continue
            s, q = t_request(it, v, tc)
            plan.append({"corpus": "T", "item_id": it["id"], "variant": v, "state": s, "questions": q, "meta": {}})
    for it in pc["items"]:
        for v in P_VARIANTS:
            if v == "N" and not n_subset(it["id"]):
                continue
            s, q, order = p_request(it, v)
            plan.append({"corpus": "P", "item_id": it["id"], "variant": v, "state": s, "questions": q,
                         "meta": {"op_order": order}})
    for it in ic["items"]:
        for v in I_VARIANTS:
            if it["corpus"] == "T":
                s, q = t_request(it, "O", tc, prompt_override=it["prompt"])
                meta = {}
            else:
                s, q, order = p_request(it, "O", command_override=it["command"])
                meta = {"op_order": order}
            plan.append({"corpus": "I", "item_id": it["id"], "variant": v, "state": s, "questions": q, "meta": meta})
    return plan
