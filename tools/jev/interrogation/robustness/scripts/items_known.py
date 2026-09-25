"""items_known.py - 74 known-answer Circuit OS items. Ground truth from project rule text, not Jev.

case: [C0] or [C0, C1, C2, C3] (C1-C3 are hand-written paraphrases for the paraphrase experiment)
options: ordered label list for the original presentation (need_more_information last)
truth: correct label; wrong: pre-registered most plausible wrong label (cue target)
unans: the case with the decisive fact removed (correct answer: need_more_information)
opt_desc: per-item option descriptions (TRUST only; other families use the family table)
"""
from items_spec import NMI

K = []


def item(**kw):
    kw.setdefault("difficulty", "normal")
    kw.setdefault("opt_desc", {})
    K.append(kw)


# ------------------------------------------------------------------ DEF (defeater register)
item(id="DEF01", family="DEF", options=["D7", "D1", NMI], truth="D7", wrong="D1",
     case=["A reviewer notes that the LED forward voltage used in the dissipation claim was typed in from memory and never checked against the manufacturer's datasheet.",
           "According to a reviewer, the forward voltage of the LED that the dissipation claim relies on was entered from memory; nobody compared it with the maker's datasheet.",
           "Review comment: the dissipation claim uses an LED forward-voltage figure that someone recalled rather than looked up, and it has not been checked against the datasheet.",
           "The LED dissipation claim depends on a forward voltage that was written down from memory. A reviewer points out it was never verified against the part's datasheet."],
     unans="A reviewer says they have a doubt about the LED dissipation claim but does not say what the doubt is.",
     derivation="D7 covers 'claims that read ratings, forward voltages or pin tables' whose datasheet parameters are unverified; an unverified forward voltage is exactly that.")
item(id="DEF02", family="DEF", options=["D1", "D9", NMI], truth="D1", wrong="D9",
     case=["The RC low-pass cutoff claim agrees with ngspice to within 0.3 %, but nobody has ever measured a physical board built from the design.",
           "ngspice and the closed-form cutoff of the RC low-pass agree within 0.3 %, yet no one has measured a real board built from this design.",
           "The cutoff claim for the RC low-pass matches the ngspice result to 0.3 %. No physical board made from the design has been measured.",
           "Nobody has measured an actual board of the RC low-pass design; its cutoff claim is only confirmed by agreeing with ngspice to 0.3 %."],
     unans="Someone is uneasy about the RC low-pass cutoff claim but has not said why.",
     derivation="D1: 'predict() is validated against mathematics and ngspice, not hardware'; eliminated by a bench measurement. Agreement with ngspice but no board measured is D1.")
item(id="DEF03", family="DEF", options=["D2", "D7", NMI], truth="D2", wrong="D7",
     case=["The claim that pin 9 can source the LED current relies on a Thevenin model of the GPIO pin rather than on the real ATmega328P.",
           "Whether pin 9 can supply the LED current is argued from a Thevenin equivalent of the GPIO pin, not from the actual ATmega328P.",
           "The pin 9 LED-current claim is based on the Thevenin GPIO model instead of the real ATmega328P chip.",
           "To claim pin 9 can source the LED's current, the design uses a Thevenin stand-in for the pin; the genuine ATmega328P was not modelled."],
     unans="There is some doubt about the pin 9 LED current claim; the details were not recorded.",
     derivation="D2: the MCU is represented by simplified models including 'a Thevenin GPIO pin', not the device.")
item(id="DEF04", family="DEF", options=["D3", "D5", NMI], truth="D3", wrong="D5",
     case=["Next week a new user will see a generated explanation for the first time, and no engineer outside the project has ever read one without being briefed.",
           "A generated explanation will be shown to a new user for the first time next week; so far no engineer from outside the project has read one unbriefed.",
           "No outside engineer has read a generated explanation cold, and next week one will be shown to a first-time user.",
           "Next week's first-time user will be the first to see a generated explanation; nobody external to the project has read one without a briefing."],
     unans="A doubt about something that will happen next week has been raised; it is not described.",
     derivation="D3: 'no external engineer has read a generated explanation cold'; applies to the explanation layer.")
item(id="DEF05", family="DEF", options=["D5", "D3", NMI], truth="D5", wrong="D3",
     case=["The design's IntentIR was produced by the intent producer from a chat prompt, and nobody has signed its properties.",
           "The intent producer created this design's IntentIR from a chat message; its properties have not been signed by anyone.",
           "Nobody has signed the properties of this design, whose IntentIR came from the intent producer reading a chat prompt.",
           "This design's specification (IntentIR) was generated by the intent producer from what the user typed in chat, and no person has signed off its properties."],
     unans="There is a doubt about this design's specification; its origin was not recorded.",
     derivation="D5 applies to 'designs whose IntentIR provenance is llm and whose properties nobody has signed'.")
item(id="DEF06", family="DEF", options=["D9", "D1", NMI], truth="D9", wrong="D1",
     case=["The rs485_node generator is not yet under the M1 mutation matrix, so a bug in it could make predict() confidently wrong without anything catching it."],
     unans="The rs485_node generator has an open doubt against it; the nature of the doubt is not stated.",
     derivation="D9: 'a generator bug makes predict() confidently wrong and nothing catches it'; applies to every generator not yet under the M1 matrix.")
item(id="DEF07", family="DEF", options=["D4", "D9", "D3", NMI], truth="D4", wrong="D9",
     case=["Adding the fifth generator took the owner three weeks of evenings; at that rate, extending coverage may cost more than one engineer can give."],
     unans="The owner is worried about the generator library; the worry is not described.",
     derivation="D4: 'coverage growth cost may outrun one engineer'; applies to the generator library as a whole.")
item(id="DEF08", family="DEF", options=["D6", "D2", "D9", NMI], truth="D6", wrong="D2",
     case=["A planned board combines the led_indicator block and the dht22_node block on one 5 V rail, and the proofs of each block might not combine into a claim about the board."],
     unans="A planned board has an open doubt; nobody has written down what it is.",
     derivation="D6: 'block proofs may not compose into board claims'; applies to any design built from more than one generator; first tested when two generators share a rail.")
item(id="DEF09", family="DEF", options=["D8", "D1", "D7", NMI], truth="D8", wrong="D1",
     case=["A z3 proof of the RC cutoff frequency has to handle pi, which cannot be represented exactly as a rational number."],
     unans="A z3 proof raised a concern; the concern was not recorded.",
     derivation="D8: 'pi is irrational, so a z3 encoding of a cutoff frequency must bracket it'.")
item(id="DEF10", family="DEF", options=["D7", "D2", "D5", NMI], truth="D7", wrong="D5",
     case=["The 120 ohm terminator's power rating in the rule table was an agent's reading of a datasheet, and nobody has verified it."],
     unans="Something about the 120 ohm terminator is in doubt; details are missing.",
     derivation="D7: datasheet parameters feeding the rule tables are unverified; applies to claims that read ratings. A power rating is a rating.")
item(id="DEF11", family="DEF", options=["D2", "D7", "D6", NMI], truth="D2", wrong="D7",
     case=["The DHT22 data-line pull-up claim relies on the MCU input being modelled as a resistor rather than as the actual microcontroller."],
     unans="The DHT22 pull-up claim has a doubt against it; the doubt is not described.",
     derivation="D2: the MCU is represented by simplified electrical models, not the device; applies to claims whose scope.model names an MCU model.")
item(id="DEF12", family="DEF", options=["D1", "D9", "D8", NMI], truth="D1", wrong="D9",
     case=["An engineer asks whether the ngspice match proves that the voltage divider behaves the same way on a real breadboard."],
     unans="An engineer asked a question about the voltage divider; the question was not recorded.",
     derivation="D1: validated against maths and ngspice, not hardware; eliminated only by a bench measurement.")

# ------------------------------------------------------------------ GRD (grade from method)
item(id="GRD01", family="GRD", options=["G5", "G6", NMI], truth="G5", wrong="G6",
     case=["The cutoff claim was checked by running ngspice once with every component at its nominal value.",
           "To check the cutoff claim, ngspice was run a single time with all components at nominal values.",
           "One ngspice simulation, all parts at their nominal values, is the only check behind the cutoff claim.",
           "The cutoff claim rests on a single ngspice run in which each component took its nominal value."],
     unans="The cutoff claim was checked by the usual method.",
     derivation="ngspice_nominal (one ngspice simulation at nominal values) -> G5.")
item(id="GRD02", family="GRD", options=["G1", "G0", NMI], truth="G1", wrong="G0",
     case=["z3 found no counterexample to the property anywhere in the tolerance box.",
           "Over the whole tolerance box, z3 could not find a single counterexample to the property.",
           "The property was checked with z3, which returned UNSAT: no counterexample exists in the tolerance box.",
           "Searching the complete tolerance box, z3 reported that no counterexample to the property exists."],
     unans="The property was checked by a solver; the outcome was not recorded.",
     derivation="z3_unsat (no counterexample over the declared box) -> G1.")
item(id="GRD03", family="GRD", options=["G6", "G5", NMI], truth="G6", wrong="G5",
     case=["The divider ratio was checked on 1,000 random draws of the resistor tolerances.",
           "1,000 random samples of the resistor tolerances were used to check the divider ratio.",
           "To check the divider ratio, the resistor tolerances were sampled at random 1,000 times.",
           "The divider ratio's check consisted of 1,000 randomly drawn combinations of resistor tolerances."],
     unans="The divider ratio was checked; the method was not recorded.",
     derivation="sampled (random samples of the parameter space) -> G6.")
item(id="GRD04", family="GRD", options=["G7", "G6", NMI], truth="G7", wrong="G6",
     case=["The rule i2c_pullups_present was not assessed on this design.",
           "On this design, nobody assessed the rule i2c_pullups_present.",
           "The i2c_pullups_present rule was left unassessed for this design.",
           "This design never had the rule i2c_pullups_present assessed."],
     unans="The rule i2c_pullups_present appears in this design's claims table.",
     derivation="'A rule that was not assessed on a design is shown as a critical row graded G7.'")
item(id="GRD05", family="GRD", options=["G2", "G1", NMI], truth="G2", wrong="G1",
     case=["Interval arithmetic produced a sound enclosure of every possible output voltage."],
     unans="Some arithmetic was done on the output voltage.",
     derivation="sound_enclosure (interval arithmetic enclosing every possible value) -> G2.")
item(id="GRD06", family="GRD", options=["G0", "G1", "G3", NMI], truth="G0", wrong="G3",
     case=["An independent proof checker replayed the proof and accepted it."],
     unans="Someone looked at the proof.",
     derivation="proof_checked (the proof was checked by a proof checker) -> G0.")
item(id="GRD07", family="GRD", options=["G1", "G4", "G6", NMI], truth="G1", wrong="G4",
     case=["Every path between the two nets was enumerated exhaustively on the netlist exactly as written."],
     unans="Some paths between the two nets were looked at.",
     derivation="exact_graph_check (exhaustive over the design as written) -> G1.")
item(id="GRD08", family="GRD", options=["G4", "G1", "G6", NMI], truth="G4", wrong="G1",
     case=["A bounded model check explored every firmware state up to depth 20."],
     unans="The firmware states were explored in some way.",
     derivation="bounded_model_check (all states explored up to a bound) -> G4.")
item(id="GRD09", family="GRD", options=["G7", "G5", "G1", NMI], truth="G7", wrong="G5",
     case=["The engineer states that the pull-up value is adequate; no check was run."],
     unans="The engineer has a view about the pull-up value.",
     derivation="asserted (stated; no check was run) -> G7.")
item(id="GRD10", family="GRD", options=["G1", "G5", "G2", NMI], truth="G1", wrong="G2",
     case=["The dissipation formula was evaluated exactly, in closed form, at the declared nominal values."],
     unans="The dissipation was estimated.",
     derivation="closed_form (an exact formula at the declared nominal scope) -> G1.")

# ------------------------------------------------------------------ X5 (retry policy)
X5_OPTS = ["no_retry_503", "no_retry_422", "retry_once", "refuse_out_of_catalogue", NMI]
item(id="X501", family="X5", options=X5_OPTS, truth="no_retry_503", wrong="retry_once",
     case=["While producing the IntentIR, the model provider returned HTTP 529 (overloaded).",
           "The model provider answered HTTP 529, meaning overloaded, during IntentIR production.",
           "IntentIR production hit an HTTP 529 overload response from the model provider.",
           "During the call that produces the IntentIR, the provider reported it was overloaded (HTTP 529)."],
     unans="Producing the IntentIR failed; the error was not logged.",
     derivation="An overload from the model provider is an API error -> no retry, HTTP 503.")
item(id="X502", family="X5", options=X5_OPTS, truth="no_retry_422", wrong="retry_once",
     case=["The forced tool_use input came back without the required field 'requirements', so it fails the IntentIR schema.",
           "The tool_use input the model was forced to return lacks the mandatory 'requirements' field and does not validate against the IntentIR schema.",
           "Schema validation of the forced tool_use input failed: the required 'requirements' field is missing.",
           "The model's forced tool_use output omitted 'requirements', a required field, so the IntentIR schema rejects it."],
     unans="The tool_use input came back, but nobody recorded whether it was valid.",
     derivation="Tool input failing the IntentIR schema is a schema failure -> no retry, HTTP 422 with the raw tool input.")
item(id="X503", family="X5", options=X5_OPTS, truth="retry_once", wrong="no_retry_422",
     case=["The tool input was schema-valid, but rc_lowpass's envelope refused it because the load resistance the prompt states had not been recorded in the IntentIR.",
           "rc_lowpass's envelope rejected a schema-valid tool input: the prompt gives a load resistance, but it was left out of the IntentIR.",
           "Although the tool input passed the schema, the rc_lowpass envelope refused it; the load resistance stated in the prompt was never recorded.",
           "A valid tool input was turned down by the rc_lowpass envelope because the IntentIR is missing the load resistance that the user's prompt actually specifies."],
     unans="A generator's envelope refused the request; the reason was not recorded.",
     derivation="Schema-valid input refused by an envelope, fixable by adding a value the prompt states -> semantic refusal -> retry once (may add, never change).")
item(id="X504", family="X5", options=X5_OPTS, truth="refuse_out_of_catalogue", wrong="retry_once",
     case=["The user asked for a 12 V to 5 V buck converter; no generator in the catalogue covers switching converters."],
     unans="The user asked for a circuit; the request text was lost.",
     derivation="A request no generator could ever cover is refused, not negotiated -> no retry.")
item(id="X505", family="X5", options=X5_OPTS, truth="no_retry_503", wrong="no_retry_422",
     case=["The model provider rejected the API key with HTTP 401 during intent production."],
     unans="Intent production stopped with an error code that was not captured.",
     derivation="An authentication error from the provider is an API error -> no retry, HTTP 503.")
item(id="X506", family="X5", options=X5_OPTS, truth="no_retry_422", wrong="retry_once",
     case=["The tool input gave cutoff_hz as the string 'one thousand' where the IntentIR schema requires a number."],
     unans="The tool input contained a value someone thought looked odd.",
     derivation="A type error against the IntentIR schema is a schema failure -> no retry, HTTP 422.")

# ------------------------------------------------------------------ ROUTE (generator routing)
RO = ["rc_lowpass", "voltage_divider", "led_indicator", "dht22_node", "rs485_node", "refuse_out_of_catalogue", NMI]
item(id="ROUTE01", family="ROUTE", options=RO, truth="led_indicator", wrong="voltage_divider",
     case=["User: I want to blink a red LED from pin 9 of my Arduino Uno, with a resistor so it doesn't burn out.",
           "User: Can you make a red LED on pin 9 of my Uno flash? Put a resistor in so the LED survives.",
           "User: Red LED, Arduino Uno pin 9, blinking, and a resistor to protect it please.",
           "User: My Uno should blink a red LED connected to pin 9; add a series resistor so it won't burn out."],
     unans="User: I need a circuit for my Arduino project.",
     derivation="An LED on an MCU GPIO pin with a current-limiting resistor is led_indicator (TPL_003).")
item(id="ROUTE02", family="ROUTE", options=RO, truth="rc_lowpass", wrong="voltage_divider",
     case=["User: Filter out noise above 1 kHz from my sensor signal using just a resistor and a capacitor.",
           "User: Using only a resistor and a capacitor, remove the noise above 1 kHz from my sensor signal.",
           "User: My sensor signal has noise above 1 kHz; I want a resistor-capacitor filter to get rid of it.",
           "User: Please give me an R and a C that cut the noise above 1 kHz out of my sensor's signal."],
     unans="User: My sensor signal has a problem; can you help?",
     derivation="A resistor-capacitor filter removing content above a cutoff is a passive RC low-pass: rc_lowpass (TPL_004).")
item(id="ROUTE03", family="ROUTE", options=RO, truth="voltage_divider", wrong="rc_lowpass",
     case=["User: Get 3.3 V from my 5 V rail with two resistors to feed an ADC reference.",
           "User: I want two resistors that turn my 5 V rail into 3.3 V for an ADC reference.",
           "User: With a pair of resistors, derive 3.3 V from the 5 V rail as my ADC reference.",
           "User: My ADC reference needs 3.3 V; make it from the 5 V supply using two resistors."],
     unans="User: I need a different voltage somewhere on my board.",
     derivation="Two resistors dividing a supply to a lower target voltage is voltage_divider (TPL_005).")
item(id="ROUTE04", family="ROUTE", options=RO, truth="dht22_node", wrong="rs485_node",
     case=["User: Log greenhouse temperature and humidity with a DHT22 on an ESP32 and alert me above 30 C.",
           "User: Use a DHT22 on my ESP32 to record the greenhouse's temperature and humidity, with an alert if it goes over 30 C.",
           "User: ESP32 plus DHT22 in the greenhouse: track temperature and humidity and warn me past 30 C.",
           "User: I want my ESP32 to read a DHT22 in the greenhouse for temperature and humidity and raise an alert above 30 C."],
     unans="User: I want to monitor my greenhouse.",
     derivation="An MCU reading a DHT22 temperature/humidity sensor with an alert threshold is dht22_node (TPL_001).")
item(id="ROUTE05", family="ROUTE", options=RO, truth="rs485_node", wrong="dht22_node",
     case=["User: Poll three Modbus RTU energy meters over RS-485 from an Arduino.",
           "User: My Arduino should read three energy meters that speak Modbus RTU on an RS-485 bus.",
           "User: Three Modbus RTU power meters on RS-485 need to be polled by an Arduino acting as master.",
           "User: Have an Arduino query three RS-485 energy meters using Modbus RTU."],
     unans="User: I need to talk to some meters.",
     derivation="An MCU acting as Modbus RTU master over RS-485 (MAX485) is rs485_node (TPL_002).")
item(id="ROUTE06", family="ROUTE", options=RO, truth="refuse_out_of_catalogue", wrong="voltage_divider",
     case=["User: Design a 24 VAC to 3.3 V switching power supply for a thermostat."],
     unans="User: I need a power supply.",
     derivation="A switching power supply is none of the five generators -> refused as out of catalogue.")
item(id="ROUTE07", family="ROUTE", options=RO, truth="refuse_out_of_catalogue", wrong="led_indicator",
     case=["User: Drive a 12 V brushed DC motor with PWM speed control from my Uno."],
     unans="User: I want my Uno to control something.",
     derivation="A PWM motor driver is none of the five generators -> refused.")
item(id="ROUTE08", family="ROUTE", options=RO, truth="led_indicator", wrong="voltage_divider",
     case=["User: A current-limited power-on status light driven by a pin of my Blackpill board."],
     unans="User: Something for my Blackpill board.",
     derivation="A status LED on a GPIO pin with current limiting is led_indicator; blackpill_f411ce is a supported board.")
item(id="ROUTE09", family="ROUTE", options=RO, truth="voltage_divider", wrong="rc_lowpass",
     case=["User: Scale a 0-10 V industrial signal down to 0-3.3 V for the ADC, with resistors only."],
     unans="User: My industrial signal needs to reach the ADC somehow.",
     derivation="Two resistors dividing a voltage to a lower target is voltage_divider.")
item(id="ROUTE10", family="ROUTE", options=RO, truth="rc_lowpass", wrong="voltage_divider",
     case=["User: A passive anti-aliasing filter in front of my ADC with a 500 Hz cutoff."],
     unans="User: Something to go in front of my ADC.",
     derivation="A passive low-pass (anti-aliasing) filter for a cutoff frequency is rc_lowpass.")
item(id="ROUTE11", family="ROUTE", options=RO, truth="refuse_out_of_catalogue", wrong="dht22_node", difficulty="hard",
     case=["User: Read a DS18B20 one-wire temperature probe from my Uno."],
     unans="User: Read a sensor from my Uno.",
     derivation="The catalogue's sensor generator is DHT22-only; a DS18B20 is not covered by any of the five -> refused (literal catalogue reading).")
item(id="ROUTE12", family="ROUTE", options=RO, truth="refuse_out_of_catalogue", wrong="rs485_node",
     case=["User: Build a CAN bus node for my car."],
     unans="User: Build a bus node.",
     derivation="CAN is not RS-485/Modbus; no generator covers it -> refused.")

# ------------------------------------------------------------------ OWN (one owner per fact)
OW = ["regen_state_py", "progress_yaml_state_json", "product_master_md", "current_phase_md", "decisions_md", "claude_md", NMI]
item(id="OWN01", family="OWN", options=OW, truth="decisions_md", wrong="claude_md",
     case=["An agent wants to record why ngspice was chosen over LTspice."],
     unans="An agent wants to write down a fact about the project.",
     derivation="'Why a choice was made: owned by brain/decisions.md.'")
item(id="OWN02", family="OWN", options=OW, truth="progress_yaml_state_json", wrong="current_phase_md",
     case=["After a test run, an agent wants the number of passing tests to be updated."],
     unans="An agent wants to update a number.",
     derivation="'Test counts ... owned by progress.yaml and state.json (derived by regen_state.py).'")
item(id="OWN03", family="OWN", options=OW, truth="claude_md", wrong="progress_yaml_state_json",
     case=["An agent wants the new backend/data/parts.py to appear in the documented project file tree."],
     unans="An agent wants to document a new file somewhere.",
     derivation="'The project file tree: owned by .claude/CLAUDE.md.'")
item(id="OWN04", family="OWN", options=OW, truth="current_phase_md", wrong="product_master_md",
     case=["The planner wants to list the three function-level tasks for this session."],
     unans="The planner wants to write something down.",
     derivation="'This session's tasks: owned by plan/current_phase.md.'")
item(id="OWN05", family="OWN", options=OW, truth="product_master_md", wrong="current_phase_md",
     case=["An agent wants to move the start of Phase 3 in the 5-phase roadmap."],
     unans="An agent wants to change a date.",
     derivation="'The 5-phase roadmap: owned by PRODUCT_MASTER.md.'")
item(id="OWN06", family="OWN", options=OW, truth="regen_state_py", wrong="progress_yaml_state_json",
     case=["An agent wants criterion 11 to show as met_by_substitute."],
     unans="An agent wants to change a status.",
     derivation="'Phase 1 criteria and their status: owned by tools/regen_state.py (PHASE1_CRITERIA).'")

# ------------------------------------------------------------------ TRUST (trust hierarchy)
item(id="TRUST01", family="TRUST", options=["progress_yaml", "agent_summary", NMI], truth="progress_yaml", wrong="agent_summary",
     opt_desc={"progress_yaml": "Believe progress.yaml.", "agent_summary": "Believe the agent's prose summary."},
     case=["progress.yaml marks parser.parse as verified_done; an agent's prose summary says the parser is broken.",
           "An agent's written summary claims the parser is broken, while progress.yaml records parser.parse as verified_done.",
           "Conflict: progress.yaml -> parser.parse verified_done; agent-written prose summary -> parser broken.",
           "The parser is broken according to a prose summary an agent wrote, but progress.yaml lists parser.parse as verified_done."],
     unans="Two sources disagree about whether parser.parse works; which sources they are was not recorded.",
     derivation="progress.yaml (rank 3) outranks agent-written prose summaries (rank 6).")
item(id="TRUST02", family="TRUST", options=["progress_yaml", "pytest_run", NMI], truth="pytest_run", wrong="progress_yaml",
     opt_desc={"progress_yaml": "Believe progress.yaml.", "pytest_run": "Believe the pytest run."},
     case=["A pytest run fails for test_parse, while progress.yaml still marks the function verified_done.",
           "progress.yaml still says verified_done for the function, but a fresh pytest run of test_parse fails.",
           "Conflict: pytest -> test_parse fails; progress.yaml -> verified_done.",
           "test_parse fails when pytest is run, yet progress.yaml continues to mark the function verified_done."],
     unans="Something disagrees with progress.yaml about test_parse.",
     derivation="Test results (rank 1) outrank progress.yaml (rank 3).")
item(id="TRUST03", family="TRUST", options=["source_code_scan", "architecture_md", NMI], truth="source_code_scan", wrong="architecture_md",
     opt_desc={"source_code_scan": "Believe the ast scan of the source code.", "architecture_md": "Believe brain/architecture.md."},
     case=["brain/architecture.md says the derived explainer makes zero model calls; an ast scan of ai/derived_explainer.py finds a model call.",
           "An ast scan of ai/derived_explainer.py finds a model call, whereas brain/architecture.md states the derived explainer makes no model calls.",
           "Conflict: brain/architecture.md -> derived explainer makes 0 model calls; ast scan of the source -> a model call exists.",
           "According to brain/architecture.md the derived explainer never calls a model, but scanning the source with ast turns up a model call in ai/derived_explainer.py."],
     unans="A document and something else disagree about the derived explainer.",
     derivation="Source code via ast scan (rank 2) outranks brain/*.md (rank 5).")
item(id="TRUST04", family="TRUST", options=["current_phase_md", "progress_yaml", NMI], truth="progress_yaml", wrong="current_phase_md",
     opt_desc={"current_phase_md": "Believe plan/current_phase.md.", "progress_yaml": "Believe progress.yaml."},
     case=["plan/current_phase.md says Stage 6 is finished; progress.yaml lists generators/bom/substitution.py as not_started."],
     unans="Two files disagree about whether Stage 6 is finished.",
     derivation="progress.yaml (rank 3) outranks plan/current_phase.md (rank 4).")
item(id="TRUST05", family="TRUST", options=["state_json", "mental_model_md", NMI], truth="state_json", wrong="mental_model_md",
     opt_desc={"state_json": "Believe state.json.", "mental_model_md": "Believe MENTAL_MODEL.md."},
     case=["MENTAL_MODEL.md, a prose summary, says the suite has 318 tests; state.json says 2063."],
     unans="Two documents give different test counts.",
     derivation="state.json (rank 3) outranks prose summaries (rank 6).")
item(id="TRUST06", family="TRUST", options=["knowledge_md", "simulation_output", NMI], truth="simulation_output", wrong="knowledge_md",
     opt_desc={"knowledge_md": "Believe brain/knowledge.md.", "simulation_output": "Believe the ngspice simulation output."},
     case=["An ngspice simulation output gives a cutoff of 1.02 kHz; brain/knowledge.md says 1.10 kHz."],
     unans="Two sources give different cutoff values.",
     derivation="Simulation outputs (rank 1) outrank brain/*.md (rank 5).")

# ------------------------------------------------------------------ PATCH (patch rules)
PA = ["accept", "reject_edits_circuit", "reject_uncited", "reject_version_conflict_409", "noop_not_a_version", NMI]
item(id="PATCH01", family="PATCH", options=PA, truth="accept", wrong="reject_uncited",
     case=["Command: 'make the cutoff 2 kHz'. Operation: replace /requirements/cutoff_hz with 2000, citing 'cutoff 2 kHz'. Submitted against the current version.",
           "The user said 'make the cutoff 2 kHz'. The patch replaces /requirements/cutoff_hz with 2000 and cites 'cutoff 2 kHz'; it targets the current version.",
           "Patch on the current version: one operation, replace /requirements/cutoff_hz -> 2000, citation 'cutoff 2 kHz', from the command 'make the cutoff 2 kHz'.",
           "For the command 'make the cutoff 2 kHz', an operation setting /requirements/cutoff_hz to 2000 was submitted with the citation 'cutoff 2 kHz', against the design's current version."],
     unans="An operation was submitted for the design; its path, citation and version were not recorded.",
     derivation="Path in IntentIR.requirements, cited words contain the value ('2 kHz' = 2000), current version, value changes -> accept.")
item(id="PATCH02", family="PATCH", options=PA, truth="reject_edits_circuit", wrong="accept",
     case=["Command: 'use a 2k resistor'. Operation: replace /components/R1/value with '2k', citing '2k resistor'. Submitted against the current version.",
           "The user said 'use a 2k resistor'. The operation replaces /components/R1/value with '2k' and cites '2k resistor'; it targets the current version.",
           "Patch on the current version: replace /components/R1/value -> '2k', citation '2k resistor', from the command 'use a 2k resistor'.",
           "For the command 'use a 2k resistor', an operation writing '2k' to /components/R1/value was submitted with the citation '2k resistor', against the current version."],
     unans="Command: 'use a 2k resistor'. An operation was submitted; its path was not recorded.",
     derivation="/components/R1/value is a CircuitIR path, not IntentIR.requirements -> rejected (edits the circuit).")
item(id="PATCH03", family="PATCH", options=PA, truth="reject_uncited", wrong="accept",
     case=["Command: 'make it faster'. Operation: replace /requirements/cutoff_hz with 5000, with no citation. Submitted against the current version.",
           "The user said 'make it faster'. The operation sets /requirements/cutoff_hz to 5000 but carries no citation; it targets the current version.",
           "Patch on the current version: replace /requirements/cutoff_hz -> 5000, no citation, from the command 'make it faster'.",
           "For the command 'make it faster', an uncited operation setting /requirements/cutoff_hz to 5000 was submitted against the current version."],
     unans="Command: 'make it faster'. An operation on the design was submitted; nothing else about it was recorded.",
     derivation="LLM-written operation without a verbatim citation containing the value -> rejected (uncited).")
item(id="PATCH04", family="PATCH", options=PA, truth="reject_version_conflict_409", wrong="accept",
     case=["Command: 'cutoff 1.5 kHz'. Operation: replace /requirements/cutoff_hz with 1500, citing 'cutoff 1.5 kHz'. Submitted against version 3 while the design is at version 5."],
     unans="Command: 'cutoff 1.5 kHz'. A cited operation on /requirements/cutoff_hz was submitted; the version it targets was not recorded.",
     derivation="Targets version 3, current is 5 -> 409 version_conflict.")
item(id="PATCH05", family="PATCH", options=PA, truth="noop_not_a_version", wrong="accept",
     case=["Command: 'keep the cutoff at 1 kHz'. Operation: replace /requirements/cutoff_hz with 1000, citing 'cutoff at 1 kHz'; the current requirement is already 1000. Submitted against the current version."],
     unans="Command: 'keep the cutoff at 1 kHz'. A cited operation on /requirements/cutoff_hz was submitted against the current version; the current requirement value was not recorded.",
     derivation="Requirements unchanged (1000 -> 1000) -> not a new version.")
item(id="PATCH06", family="PATCH", options=PA, truth="accept", wrong="reject_edits_circuit",
     case=["Command: 'make the LED green'. Operation: replace /requirements/led_color with 'green', citing 'LED green'. Submitted against the current version."],
     unans="Command: 'make the LED green'. An operation was submitted; its path and citation were not recorded.",
     derivation="IntentIR requirement path, cited value, current version, changes the value -> accept.")

# ------------------------------------------------------------------ SCOPE (phase scope)
SC = ["in_scope_now", "out_of_scope_later_phase", "needs_owner_approval", NMI]
item(id="SCOPE01", family="SCOPE", options=SC, truth="needs_owner_approval", wrong="in_scope_now",
     case=["Proposal: fetch live Digikey prices for every BOM line.",
           "Proposal: have every BOM line priced live from Digikey.",
           "Proposal: call the Digikey API for a live price on each line of the BOM.",
           "Proposal: replace the BOM's prices with live Digikey quotes, line by line."],
     unans="Proposal: change how the BOM gets its numbers.",
     derivation="Live pricing (X7: Digikey/LCSC live API) needs the owner's explicit approval.")
item(id="SCOPE02", family="SCOPE", options=SC, truth="out_of_scope_later_phase", wrong="in_scope_now",
     case=["Proposal: add a buck converter generator for 12 V to 5 V.",
           "Proposal: a new generator that produces a 12 V to 5 V buck converter.",
           "Proposal: extend the catalogue with a 12 V -> 5 V buck converter generator.",
           "Proposal: let Circuit OS generate buck converters stepping 12 V down to 5 V."],
     unans="Proposal: add a new generator.",
     derivation="Switching converters are out of Phase 2 (Phase 3 or later).")
item(id="SCOPE03", family="SCOPE", options=SC, truth="in_scope_now", wrong="needs_owner_approval",
     case=["Proposal: add the GET /design/{id}/bom endpoint so the BOM can be fetched.",
           "Proposal: implement GET /design/{id}/bom so clients can retrieve the BOM.",
           "Proposal: expose the BOM through a new GET /design/{id}/bom route.",
           "Proposal: build the GET /design/{id}/bom endpoint for fetching a design's BOM."],
     unans="Proposal: add an endpoint.",
     derivation="GET /design/{id}/bom is listed as in scope now (Stage 6).")
item(id="SCOPE04", family="SCOPE", options=SC, truth="out_of_scope_later_phase", wrong="in_scope_now",
     case=["Proposal: import a customer's existing KiCad netlist and recognise its blocks."],
     unans="Proposal: support a customer's request.",
     derivation="Foreign-netlist recognition is out of Phase 2.")
item(id="SCOPE05", family="SCOPE", options=SC, truth="out_of_scope_later_phase", wrong="in_scope_now",
     case=["Proposal: add via stitching to the custom A* router."],
     unans="Proposal: improve an existing engine.",
     derivation="PCB layout is out of Phase 2 and the custom A* router must not be extended.")
item(id="SCOPE06", family="SCOPE", options=SC, truth="out_of_scope_later_phase", wrong="needs_owner_approval",
     case=["Proposal: fine-tune a model on Circuit OS designs."],
     unans="Proposal: train something.",
     derivation="Fine-tuning is out of Phase 2.")
item(id="SCOPE07", family="SCOPE", options=SC, truth="out_of_scope_later_phase", wrong="in_scope_now",
     case=["Proposal: add shared team workspaces for multiple users."],
     unans="Proposal: add workspaces.",
     derivation="Team features are out of Phase 2.")
item(id="SCOPE08", family="SCOPE", options=SC, truth="in_scope_now", wrong="needs_owner_approval",
     case=["Proposal: record price_asof next to every static BOM price."],
     unans="Proposal: record an extra field in the BOM.",
     derivation="price_asof on every price is listed as in scope now (Stage 6).")

# ------------------------------------------------------------------ RULE (critical rules)
item(id="RULE01", family="RULE", options=["one_rule", "celery", "columnar_output", "complies", NMI], truth="one_rule", wrong="celery",
     case=["Proposal: have the LLM return the SPICE netlist as text and pass it straight to ngspice.",
           "Proposal: ask the LLM for the SPICE netlist as plain text and feed that text directly to ngspice.",
           "Proposal: the LLM writes the SPICE netlist itself, and ngspice simulates it as returned.",
           "Proposal: skip the IR step - take the netlist text the LLM writes and hand it to ngspice unchanged."],
     unans="Proposal: change how the netlist reaches ngspice.",
     derivation="one_rule: the LLM never writes SPICE directly.")
item(id="RULE02", family="RULE", options=["celery", "one_rule", "postgres", "complies", NMI], truth="celery", wrong="one_rule",
     case=["Proposal: run ngspice inside the /simulate route handler with await and return the result in the HTTP response.",
           "Proposal: in the /simulate handler, await an ngspice run and put its result in the HTTP response.",
           "Proposal: the /simulate route itself runs ngspice (awaited) and replies with the simulation result.",
           "Proposal: simulate inline - the /simulate HTTP handler awaits ngspice and returns what it produces."],
     unans="Proposal: change where simulations run.",
     derivation="celery: simulation always via Celery, never inline in an HTTP handler.")
item(id="RULE03", family="RULE", options=["mcu_resistor", "columnar_output", "one_rule", "complies", NMI], truth="mcu_resistor", wrong="columnar_output",
     case=["Proposal: model the Uno in the netlist as VMCU VCC_5V GND DC 5.",
           "Proposal: represent the Uno in SPICE with the line VMCU VCC_5V GND DC 5.",
           "Proposal: the netlist's MCU element becomes a 5 V DC source, VMCU VCC_5V GND DC 5.",
           "Proposal: write the Uno into the netlist as a DC voltage source: VMCU VCC_5V GND DC 5."],
     unans="Proposal: change the MCU line in the netlist.",
     derivation="mcu_resistor: the MCU SPICE model is a resistor, never a voltage source; VMCU ... DC 5 is a voltage source.")
item(id="RULE04", family="RULE", options=["columnar_output", "mcu_resistor", "celery", "complies", NMI], truth="columnar_output", wrong="mcu_resistor",
     case=["Proposal: parse ngspice batch output with the regex v\\(x\\)\\s*=\\s*(\\d+)."],
     unans="Proposal: change the ngspice output parser.",
     derivation="columnar_output: batch output is columnar; a v(x) = y regex does not match it.")
item(id="RULE05", family="RULE", options=["kicanvas_ssr", "cors_first", "one_rule", "complies", NMI], truth="kicanvas_ssr", wrong="cors_first",
     case=["Proposal: import SchematicViewer with a normal import at the top of page.tsx so it renders on the server."],
     unans="Proposal: change how page.tsx loads its components.",
     derivation="kicanvas_ssr: kicanvas via dynamic import with ssr: false; never server-rendered.")
item(id="RULE06", family="RULE", options=["postgres", "celery", "static_bom", "complies", NMI], truth="postgres", wrong="celery",
     case=["Proposal: keep generated designs in a module-level dict design_store = {} for speed."],
     unans="Proposal: change where designs are kept.",
     derivation="postgres: no in-memory design_store = {}.")
item(id="RULE07", family="RULE", options=["cors_first", "postgres", "kicanvas_ssr", "complies", NMI], truth="cors_first", wrong="postgres",
     case=["Proposal: register all routers first and add CORSMiddleware at the end of main.py."],
     unans="Proposal: reorder main.py.",
     derivation="cors_first: CORS middleware before any route is registered.")
item(id="RULE08", family="RULE", options=["complies", "postgres", "celery", "one_rule", NMI], truth="complies", wrong="postgres",
     case=["Proposal: save every design to PostgreSQL with save_design() right after generation."],
     unans="Proposal: change what happens after generation.",
     derivation="Persisting to PostgreSQL is what the postgres rule requires; no rule is violated.")

KNOWN = K
assert len(KNOWN) == 74, len(KNOWN)
assert len({k['id'] for k in KNOWN}) == 74
for k in KNOWN:
    assert k["truth"] in k["options"] and k["wrong"] in k["options"] and k["truth"] != k["wrong"], k["id"]
    assert k["options"][-1] == NMI, k["id"]
