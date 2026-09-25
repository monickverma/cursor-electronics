"""items_hard.py - 24 harder known-answer Circuit OS items ("lure" items).

Written after E1a/E3 showed the first 74 known items at ceiling (p_top ~1.0). Each item's truth
follows from the family rule text (items_spec.FAMILIES[...]["context"][0]); each has a strong,
pre-registered lure (`wrong`): a surface cue (a number, a keyword, a second fact) pointing at a
wrong option. Ground truth never comes from Jev.
"""
from items_spec import NMI

H = []


def h(**kw):
    kw.setdefault("difficulty", "lure")
    kw.setdefault("opt_desc", {})
    kw["case"] = [kw["case"]]
    H.append(kw)


PA = ["accept", "reject_edits_circuit", "reject_uncited", "reject_version_conflict_409", "noop_not_a_version", NMI]
X5 = ["no_retry_503", "no_retry_422", "retry_once", "refuse_out_of_catalogue", NMI]
RO = ["rc_lowpass", "voltage_divider", "led_indicator", "dht22_node", "rs485_node", "refuse_out_of_catalogue", NMI]
OW = ["regen_state_py", "progress_yaml_state_json", "product_master_md", "current_phase_md", "decisions_md", "claude_md", NMI]
SC = ["in_scope_now", "out_of_scope_later_phase", "needs_owner_approval", NMI]

h(id="H01", family="PATCH", options=PA, truth="reject_uncited", wrong="accept",
  case="Command: 'make the cutoff 2 kHz'. Operation: replace /requirements/cutoff_hz with 2500, citing 'cutoff 2 kHz'. Submitted against the current version.",
  derivation="The cited words must contain the value written; 'cutoff 2 kHz' does not contain 2500 -> rejected as uncited.")
h(id="H02", family="PATCH", options=PA, truth="reject_uncited", wrong="accept",
  case="Command: 'make the cutoff 2 kHz'. Operation: replace /requirements/cutoff_hz with 2000, citing 'make the cutoff'. Submitted against the current version.",
  derivation="The citation 'make the cutoff' does not contain the value written (2000 / 2 kHz) -> rejected as uncited.")
h(id="H03", family="PATCH", options=PA, truth="accept", wrong="reject_edits_circuit",
  case="Command: 'use the 4.7k resistor I have'. Operation: add /requirements/constraints/pinned/R1 with '4.7k', citing 'the 4.7k resistor'. Submitted against the current version.",
  derivation="The path is under /requirements (IntentIR.requirements), not CircuitIR; the citation contains the value; current version; it changes the requirement -> accept. The lure is the part name R1.")
h(id="H04", family="X5", options=X5, truth="no_retry_503", wrong="no_retry_422",
  case="The model provider itself returned HTTP 422 because the request exceeded its maximum context length.",
  derivation="A failure of the model provider is an API error -> no retry, HTTP 503. The 422 is the provider's status, not an IntentIR schema failure of the tool input.")
h(id="H05", family="X5", options=X5, truth="refuse_out_of_catalogue", wrong="retry_once",
  case="The tool input was schema-valid and faithfully recorded the user's request for a 2 MHz RC low-pass; every envelope refused it because no generator supports 2 MHz.",
  derivation="Nothing is missing that a retry could add, and a retry may never change the requested 2 MHz; no generator could ever cover it -> refused, not negotiated.")
h(id="H06", family="X5", options=X5, truth="retry_once", wrong="refuse_out_of_catalogue",
  case="The tool input was schema-valid, but dht22_node's envelope refused it because the alert threshold the user typed ('alert me above 30 C') was not recorded in the IntentIR.",
  derivation="Semantic refusal fixable by adding a value the user stated -> retry once.")
h(id="H07", family="TRUST", options=["decisions_md", "current_phase_md", NMI], truth="current_phase_md", wrong="decisions_md",
  opt_desc={"decisions_md": "Believe brain/decisions.md.", "current_phase_md": "Believe plan/current_phase.md."},
  case="brain/decisions.md says the Stage 6 task list was re-scoped last week; plan/current_phase.md still lists the original Stage 6 tasks. Which list of this session's tasks should the agent believe?",
  derivation="plan/current_phase.md (rank 4) outranks brain/*.md (rank 5).")
h(id="H08", family="TRUST", options=["progress_yaml", "source_code_scan", NMI], truth="source_code_scan", wrong="progress_yaml",
  opt_desc={"progress_yaml": "Believe progress.yaml.", "source_code_scan": "Believe the ast scan of the source code."},
  case="progress.yaml says generators/bom/substitution.py is not_started; an ast scan of the source finds substitution.py defining 14 functions.",
  derivation="Source code via ast scan (rank 2) outranks progress.yaml (rank 3).")
h(id="H09", family="TRUST", options=["agent_summary", "knowledge_md", NMI], truth="knowledge_md", wrong="agent_summary",
  opt_desc={"agent_summary": "Believe the agent's prose summary.", "knowledge_md": "Believe brain/knowledge.md."},
  case="An agent's prose summary, written yesterday, says the DHT22 data line needs a 4.7k pull-up; brain/knowledge.md says 10k.",
  derivation="brain/*.md (rank 5) outranks agent-written prose summaries (rank 6), regardless of recency.")
h(id="H10", family="GRD", options=["G5", "G7", "G1", NMI], truth="G7", wrong="G5",
  case="ngspice was run once at nominal values for this design, but the rule rs485_termination_present was not assessed on it. What grade does that rule's row get?",
  derivation="'A rule that was not assessed on a design is shown as a critical row graded G7'; the ngspice run is about other claims.")
h(id="H11", family="GRD", options=["G2", "G6", "G5", NMI], truth="G6", wrong="G2",
  case="Ten thousand random tolerance draws all stayed inside the limit, which the reviewer described as 'a sound enclosure'.",
  derivation="The method is random sampling (sampled) -> G6; the reviewer's words 'sound enclosure' are not the method.")
h(id="H12", family="GRD", options=["G1", "G5", "G6", NMI], truth="G5", wrong="G1",
  case="The claim's only check was one ngspice simulation at nominal values, whose result happened to equal what a closed-form formula gives.",
  derivation="The claim's method is ngspice_nominal -> G5; no closed-form evaluation was the check.")
h(id="H13", family="DEF", options=["D7", "D1", "D2", NMI], truth="D1", wrong="D7",
  case="The LED forward voltage was verified against the datasheet last week, but no board built from the design has ever been measured. Which doubt remains?",
  derivation="The datasheet figure is verified (D7 addressed); the remaining doubt is validation against maths/ngspice but not hardware -> D1.")
h(id="H14", family="DEF", options=["D2", "D5", "D3", NMI], truth="D5", wrong="D2",
  case="The IntentIR for this ESP32 design was written by the LLM intent producer, and nobody has signed its properties. The MCU is not involved in any claim.",
  derivation="LLM-provenance IntentIR with unsigned properties -> D5; D2 needs a claim naming an MCU model.")
h(id="H15", family="DEF", options=["D1", "D9", "D8", NMI], truth="D9", wrong="D1",
  case="ngspice agrees with predict() for rs485_node, but ngspice simulates the same netlist the generator wrote, so a generator bug would fool both; rs485_node is not under the M1 matrix.",
  derivation="A generator bug making predict() confidently wrong undetected, generator not under M1 -> D9.")
h(id="H16", family="ROUTE", options=RO, truth="refuse_out_of_catalogue", wrong="rc_lowpass",
  case="User: I need an RC high-pass filter at 50 Hz to block DC from my microphone signal.",
  derivation="The catalogue has an RC low-pass only; a high-pass is not covered -> refused.")
h(id="H17", family="ROUTE", options=RO, truth="refuse_out_of_catalogue", wrong="dht22_node",
  case="User: Read a BME280 temperature, humidity and pressure sensor over I2C from my Uno.",
  derivation="The sensor generator is DHT22-only; a BME280 is not in the catalogue -> refused.")
h(id="H18", family="ROUTE", options=RO, truth="rs485_node", wrong="refuse_out_of_catalogue",
  case="User: My Blackpill should act as Modbus RTU master to one variable-frequency drive on an RS-485 line.",
  derivation="An MCU as Modbus RTU master on RS-485 is rs485_node; the drive is just the slave device; blackpill_f411ce is supported.")
h(id="H19", family="SCOPE", options=SC, truth="out_of_scope_later_phase", wrong="in_scope_now",
  case="Proposal: add a switching power-stage generator so the Stage 6 BOM has more parts to substitute.",
  derivation="Switching converters are out of Phase 2, whatever the BOM motivation.")
h(id="H20", family="RULE", options=["celery", "complies", "one_rule", "postgres", NMI], truth="complies", wrong="celery",
  case="Proposal: the /simulate route calls run_simulation.apply_async(...) and immediately returns the job_id; the client polls for the result.",
  derivation="This is the Celery pattern the celery rule requires; no rule is violated.")
h(id="H21", family="RULE", options=["complies", "one_rule", "static_bom", "celery", NMI], truth="one_rule", wrong="complies",
  case="Proposal: the LLM returns JSON with a 'firmware' field holding the full .ino source; the JSON is validated against a schema and the .ino is written to disk.",
  derivation="The LLM still writes firmware directly; a JSON wrapper does not make it IR -> deterministic compiler -> one_rule violated.")
h(id="H22", family="RULE", options=["complies", "mcu_resistor", "columnar_output", "one_rule", NMI], truth="mcu_resistor", wrong="complies",
  case="Proposal: model the ESP32 as R_MCU_U1 VCC_3V3 GND 41 and also add VREF_U1 VCC_3V3 GND DC 3.3 to hold the MCU's rail steady.",
  derivation="Adding a voltage source for the MCU violates 'the MCU SPICE model is a resistor, never a voltage source'.")
h(id="H23", family="OWN", options=OW, truth="decisions_md", wrong="current_phase_md",
  case="An agent wants to record that Stage 6 will skip the 5% KPI, and why.",
  derivation="'Why a choice was made: owned by brain/decisions.md.' The Stage 6 mention is the lure.")
h(id="H24", family="OWN", options=OW, truth="progress_yaml_state_json", wrong="regen_state_py",
  case="An agent wants the verified percentage to include the newly registered modules. Which file owns that number?",
  derivation="'Test counts, verified percentage, module status: owned by progress.yaml and state.json (derived by regen_state.py)'.")

HARD = H
assert len(HARD) == 24
for k in HARD:
    assert k["truth"] in k["options"] and k["wrong"] in k["options"] and k["truth"] != k["wrong"] and k["options"][-1] == NMI, k["id"]
