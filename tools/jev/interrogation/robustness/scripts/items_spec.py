"""items_spec.py - hand-authored, project-derived item bank for the Jev robustness interrogation.

Ground truth never comes from Jev. Every known-answer item carries `truth` and a `derivation`
that cites the Circuit OS rule text in the family's `context` (itself quoted or condensed from
the p2 snapshot / handoff: validation/defeaters.py, validation/claims.py, decisions.md X5 and
X2/X4 entries, AGENTS.md, CLAUDE.md, handoff 2026-09-25 sections 2 and 9).

Family fields:
  context[0..3]      R0 = original rules text; R1-R3 = paraphrases (same facts, new wording)
  instructions[0..3] I0 = original; I1-I3 = paraphrases
  options            label -> "choose when" description (the item picks a subset)
Item fields:
  id, family, case[0..3] (C0 original; C1-C3 paraphrases where written), options (ordered subset,
  need_more_information always last), truth, wrong (pre-registered most plausible wrong option,
  used as the target of wrong-direction cues), unans (case with the decisive fact removed; the
  correct answer is need_more_information), derivation, difficulty.
"""

NMI = "need_more_information"
NMI_DESC = "The state does not contain enough information to choose any other option."

# Clearly inapplicable options, used only to vary k (confidence formula) and to test dead-option
# inflation. None can apply to any Circuit OS item.
DEAD_OPTIONS = {
    "office_coffee_supply": "Choose when the case is about restocking the office coffee supply.",
    "marketing_slogan": "Choose when the case is about the wording of a marketing slogan.",
    "weather_forecast": "Choose when the case is about tomorrow's weather forecast.",
    "font_licensing": "Choose when the case is about licensing a typeface for the website.",
    "parking_permit": "Choose when the case is about an employee parking permit.",
    "holiday_calendar": "Choose when the case is about the company holiday calendar.",
}

FAMILIES = {}

# ---------------------------------------------------------------- DEF: defeater identification
FAMILIES["DEF"] = {
    "source": "p2/backend/validation/defeaters.py REGISTER (D1-D9)",
    "context": [
        # R0
        "Defeater register of Circuit OS (backend/validation/defeaters.py). A defeater is a recorded doubt about a claim; a claim that cites an open defeater is reported as defeasible.\n"
        "D1. Doubt: predict() is validated against mathematics and ngspice, not hardware. Applies to: every closed-form or simulated claim about circuit behaviour. Eliminated by: a bench measurement agreeing within tolerance.\n"
        "D2. Doubt: the MCU is represented by simplified electrical models (a resistive supply load sized from its run current, and a Thevenin GPIO pin), not the device. Applies to: claims whose scope.model names an MCU model. Eliminated by: reachset conformance against the real device.\n"
        "D3. Doubt: no external engineer has read a generated explanation cold. Applies to: the explanation layer. Eliminated by: criterion 12's review.\n"
        "D4. Doubt: coverage growth cost may outrun one engineer. Applies to: the generator library as a whole. Eliminated by: measured authoring cost per generator.\n"
        "D5. Doubt: an LLM may write the IntentIR, so the specification is untrusted. Applies to: designs whose IntentIR provenance is llm and whose properties nobody has signed. Eliminated by: a person signing the back-translated properties.\n"
        "D6. Doubt: block proofs may not compose into board claims. Applies to: any design built from more than one generator. Eliminated by: interface contracts, first tested when two generators share a rail.\n"
        "D7. Doubt: datasheet parameters feeding predict() and the rule tables are unverified. Applies to: claims that read ratings, forward voltages or pin tables. Eliminated by: provenance per parameter.\n"
        "D8. Doubt: pi is irrational, so a z3 encoding of a cutoff frequency must bracket it. Applies to: z3-proved claims involving pi or another transcendental. Eliminated by: rational bracketing in the proof compiler.\n"
        "D9. Doubt: a generator bug makes predict() confidently wrong and nothing catches it. Applies to: every generator not yet under the M1 mutation matrix. Eliminated by: the M1 matrix detecting seeded faults in that generator's output.",
        # R1
        "Circuit OS keeps a register of defeaters, each one a documented reason to doubt a claim; any claim citing an open defeater is shown as defeasible.\n"
        "D1: the only checks on predict() are mathematics and ngspice simulation, never physical hardware. It concerns all simulated or closed-form claims about how a circuit behaves, and it goes away once a bench measurement agrees within tolerance.\n"
        "D2: instead of the real microcontroller, the models use simplifications: a resistor standing in for its supply load (sized from run current) and a Thevenin equivalent for a GPIO pin. It concerns claims whose scope.model names an MCU model, and it goes away with reachset conformance against the actual device.\n"
        "D3: nobody outside the project has yet read a generated explanation without a briefing. It concerns the explanation layer and goes away with the criterion 12 review.\n"
        "D4: the cost of growing coverage might exceed what a single engineer can sustain. It concerns the whole generator library and goes away when authoring cost per generator is measured.\n"
        "D5: because an LLM may have written the IntentIR, the specification cannot be trusted. It concerns designs with llm-provenance IntentIR whose properties no one has signed, and it goes away when a person signs the back-translated properties.\n"
        "D6: proofs about individual blocks might not combine into claims about a whole board. It concerns designs assembled from more than one generator and goes away with interface contracts.\n"
        "D7: the datasheet figures that feed predict() and the rule tables have not been verified. It concerns claims that read ratings, forward voltages or pin tables, and it goes away with per-parameter provenance.\n"
        "D8: since pi is irrational, a z3 encoding of a cutoff frequency has to bracket it. It concerns z3-proved claims involving pi or other transcendentals and goes away with rational bracketing in the proof compiler.\n"
        "D9: a bug in a generator could make predict() confidently wrong with nothing to catch it. It concerns every generator not yet covered by the M1 mutation matrix and goes away when that matrix detects seeded faults in the generator's output.",
        # R2
        "Register of recorded doubts (defeaters) used by Circuit OS claims. Format: ID - what is in doubt - which claims it touches - what would retire it.\n"
        "D1 - predict() has been confirmed by maths and by ngspice but never on hardware - any closed-form or simulated statement about circuit behaviour - a bench reading that matches within tolerance.\n"
        "D2 - the microcontroller is stood in for by simple electrical models (a supply-load resistor derived from run current; a Thevenin model of a GPIO pin) instead of the part itself - claims whose scope.model names an MCU model - reachset conformance with the physical device.\n"
        "D3 - no independent engineer has read a generated explanation cold - the explanation layer - the review defined by criterion 12.\n"
        "D4 - the effort of extending coverage may be more than one engineer can supply - the generator library overall - a measured authoring cost for each generator.\n"
        "D5 - the IntentIR might have been written by an LLM, so the spec is not trusted - designs whose IntentIR came from an llm and whose properties are unsigned - a person signing off the back-translated properties.\n"
        "D6 - proofs of separate blocks might not add up to claims about the board - designs combining two or more generators - interface contracts.\n"
        "D7 - datasheet values used by predict() and by the rule tables are not verified - claims relying on ratings, forward voltages or pin tables - recorded provenance for each parameter.\n"
        "D8 - pi cannot be represented exactly, so z3 must bracket it when encoding a cutoff frequency - z3 proofs involving pi or other transcendental numbers - rational bracketing inside the proof compiler.\n"
        "D9 - a generator defect could leave predict() confidently wrong and undetected - generators not yet under the M1 mutation matrix - the M1 matrix catching seeded faults in that generator.",
        # R3
        "The Circuit OS defeater list. Each entry names a doubt that can undermine a claim, what it covers, and how it is cleared.\n"
        "D1 covers circuit-behaviour claims (closed-form or simulated): predict() was checked against theory and ngspice only, not real hardware. Cleared by a bench measurement within tolerance.\n"
        "D2 covers claims whose scope.model mentions an MCU model: the microcontroller is approximated (resistive supply load from run current, Thevenin GPIO pin) rather than modelled as the actual chip. Cleared by reachset conformance on the real device.\n"
        "D3 covers the explanation layer: an outside engineer has never read a generated explanation cold. Cleared by the criterion 12 review.\n"
        "D4 covers the generator library as a whole: expanding coverage may cost more than one engineer can give. Cleared by measuring authoring cost per generator.\n"
        "D5 covers designs with LLM-written IntentIR and unsigned properties: the specification is untrusted because a language model may have produced it. Cleared when a person signs the back-translated properties.\n"
        "D6 covers designs built from several generators: block-level proofs may fail to compose into board-level claims. Cleared by interface contracts.\n"
        "D7 covers claims that read ratings, forward voltages or pin tables: the datasheet parameters behind predict() and the rule tables are unverified. Cleared by provenance for every parameter.\n"
        "D8 covers z3 proofs that involve pi or other transcendentals: pi is irrational, so the encoding of a cutoff has to bracket it. Cleared by rational bracketing in the proof compiler.\n"
        "D9 covers every generator outside the M1 mutation matrix: a generator bug could make predict() confidently wrong without detection. Cleared when the M1 matrix detects seeded faults in its output.",
    ],
    "instructions": [
        "Which defeater in the register records the doubt described in the case?",
        "The case raises a doubt. Which register entry is that doubt?",
        "Identify the defeater ID whose recorded doubt matches the situation described in the case.",
        "Under which defeater from the register should the doubt in the case be filed?",
    ],
    "options": {
        "D1": "The doubt is that circuit behaviour was checked only against maths or ngspice, not against hardware.",
        "D2": "The doubt is that the MCU is modelled by a simplified electrical model instead of the real device.",
        "D3": "The doubt is that no external engineer has read a generated explanation cold.",
        "D4": "The doubt is that the cost of growing generator coverage may outrun one engineer.",
        "D5": "The doubt is that an LLM-written, unsigned IntentIR makes the specification untrusted.",
        "D6": "The doubt is that proofs of separate blocks may not compose into claims about a board.",
        "D7": "The doubt is that datasheet parameters (ratings, forward voltages, pin tables) are unverified.",
        "D8": "The doubt is that pi (or another transcendental) must be bracketed in a z3 encoding.",
        "D9": "The doubt is that a generator bug could make predict() confidently wrong without detection.",
        NMI: NMI_DESC,
    },
    "prop": "the doubt in the case is the one recorded as {L}",
    "negprop": "the doubt in the case is recorded under a defeater other than {L}",
}

# ---------------------------------------------------------------- GRD: grade from method
FAMILIES["GRD"] = {
    "source": "p2/backend/validation/claims.py METHOD_GRADE and Claim validator (not assessed -> G7)",
    "context": [
        "How Circuit OS grades a claim (backend/validation/claims.py). A claim's grade is derived from its checking method through one table; it is never typed per claim.\n"
        "proof_checked (the proof was checked by a proof checker) -> G0\n"
        "z3_unsat (z3 finds no counterexample over the declared box) -> G1\n"
        "monotone_corners (exact when monotone in every argument; the corners are evaluated) -> G1\n"
        "closed_form (an exact formula at the declared nominal scope) -> G1\n"
        "exact_graph_check (exhaustive over the design as written) -> G1\n"
        "sound_enclosure (interval arithmetic enclosing every possible value) -> G2\n"
        "certificate -> G3\n"
        "bounded_model_check (all states explored up to a bound) -> G4\n"
        "ngspice_nominal (one ngspice simulation at nominal values) -> G5\n"
        "sampled (random samples of the parameter space) -> G6\n"
        "asserted (stated; no check was run) -> G7\n"
        "A rule that was not assessed on a design is shown as a critical row graded G7.",
        "Circuit OS never lets anyone type a grade onto a claim; the grade follows from how the claim was checked, via a single table in backend/validation/claims.py.\n"
        "G0: the proof was verified by a proof checker (proof_checked).\n"
        "G1: z3 reports no counterexample anywhere in the declared box (z3_unsat); or the corners were evaluated for a function monotone in every argument (monotone_corners); or an exact formula was evaluated at the declared nominal scope (closed_form); or the design as written was searched exhaustively (exact_graph_check).\n"
        "G2: interval arithmetic gives an enclosure containing every possible value (sound_enclosure).\n"
        "G3: certificate.\n"
        "G4: every state was explored up to a bound (bounded_model_check).\n"
        "G5: a single ngspice run at nominal values (ngspice_nominal).\n"
        "G6: random samples drawn from the parameter space (sampled).\n"
        "G7: the claim is merely stated with no check run (asserted); a rule not assessed on a design also appears as a critical G7 row.",
        "Grade table (claims.py). Checking method, then grade:\n"
        "- checked by a proof checker: G0\n"
        "- z3 returns UNSAT, i.e. no counterexample in the declared box: G1\n"
        "- corner evaluation of a function that is monotone in each argument: G1\n"
        "- exact closed-form evaluation at the declared nominal scope: G1\n"
        "- exhaustive check over the design exactly as written: G1\n"
        "- sound interval enclosure of all possible values: G2\n"
        "- certificate: G3\n"
        "- bounded model check exploring all states to a bound: G4\n"
        "- one ngspice simulation at nominal values: G5\n"
        "- random sampling of the parameter space: G6\n"
        "- assertion without any check: G7\n"
        "The grade always comes from the method; it is never assigned by hand. A rule left unassessed on a design is listed as a critical G7 row.",
        "In Circuit OS the method used to check a claim fixes its grade through one lookup table (backend/validation/claims.py), so no claim carries a hand-written grade. "
        "Proof-checked proofs get G0. G1 goes to four exact methods: z3 finding no counterexample over the declared box, evaluating the corners of a function monotone in every argument, an exact closed-form formula at the declared nominal scope, and an exhaustive check of the design as written. "
        "A sound interval-arithmetic enclosure of every possible value is G2. A certificate is G3. A bounded model check that explores all states up to a bound is G4. One ngspice simulation at nominal values is G5. Random sampling of the parameter space is G6. "
        "A claim that is only asserted, with no check run, is G7, and so is a rule that was not assessed on the design, which appears as a critical row.",
    ],
    "instructions": [
        "What grade does the claim in the case receive?",
        "Using the method-to-grade table, which grade applies to the claim described in the case?",
        "Assign the grade that the claim's checking method earns under the table.",
        "Given how the claim in the case was checked, which grade does the table give it?",
    ],
    "options": {
        "G0": "The grade for claims whose proof was checked by a proof checker.",
        "G1": "The grade for z3_unsat, monotone_corners, closed_form or exact_graph_check claims.",
        "G2": "The grade for sound_enclosure claims.",
        "G3": "The grade for certificate claims.",
        "G4": "The grade for bounded_model_check claims.",
        "G5": "The grade for ngspice_nominal claims.",
        "G6": "The grade for sampled claims.",
        "G7": "The grade for asserted claims and for rules not assessed.",
        NMI: NMI_DESC,
    },
    "prop": "the claim in the case receives grade {L}",
    "negprop": "the claim in the case receives a grade other than {L}",
}

# ---------------------------------------------------------------- X5: retry policy
FAMILIES["X5"] = {
    "source": "p2 decisions.md [2026-09-21] X5 accepted; handoff section 2 (Retries X5)",
    "context": [
        "Circuit OS retry policy for producing the IntentIR from a prompt (amendment X5; backend/ai/intent_producer.py).\n"
        "- API error (the model provider fails: outage, overload, authentication or rate-limit error): do not retry; return HTTP 503.\n"
        "- Schema failure (the forced tool_use input does not validate against the IntentIR schema): do not retry; return HTTP 422 carrying the raw tool input.\n"
        "- Semantic refusal (the input is valid but no generator's envelope() accepts it): retry once; the retry may add a value it failed to record the first time, but may never change or drop a value the user asked for.\n"
        "- A request genuinely outside the catalogue (none of the five generators could ever cover it) is refused, not negotiated: no retry.",
        "How Circuit OS reacts when turning a prompt into an IntentIR goes wrong (X5, implemented in backend/ai/intent_producer.py):\n"
        "- If the model provider itself fails (it is down, overloaded, rejects the credentials or rate-limits the call), nothing is retried and the response is HTTP 503.\n"
        "- If the tool_use input the model was forced to produce fails validation against the IntentIR schema, nothing is retried and the response is HTTP 422 with the raw tool input attached.\n"
        "- If the input is valid but every generator's envelope() rejects it, one retry is allowed; that retry may fill in a value missed the first time, but it must not alter or remove anything the user asked for.\n"
        "- If the request lies truly outside the catalogue, so that none of the five generators could ever handle it, it is refused outright and not retried.",
        "Retry rules for intent production (X5):\n"
        "1. Provider-side API failure (outage, overload, bad credentials, rate limit) -> no retry, HTTP 503.\n"
        "2. The forced tool_use payload fails IntentIR schema validation -> no retry, HTTP 422 including the raw tool input.\n"
        "3. Schema-valid input refused by every generator envelope() -> exactly one retry, which may add a value that was not recorded the first time but may not change or drop any value the user requested.\n"
        "4. A request no generator in the five-generator catalogue could ever cover -> refused, never negotiated, no retry.",
        "Under amendment X5, Circuit OS treats failures during IntentIR production differently depending on their cause. "
        "When the model provider errors out (for example it is unavailable, overloaded, refuses the API key or applies a rate limit), the system does not try again and answers HTTP 503. "
        "When the tool_use output is not valid under the IntentIR schema, it also does not try again; it answers HTTP 422 and includes the raw tool input. "
        "When the output is valid but no generator's envelope() will accept it, it tries exactly once more, and that second attempt may only add a value that was previously left out, never change or delete a value the user specified. "
        "When the request is something the five-generator catalogue could never cover, it is refused rather than negotiated, without any retry.",
    ],
    "instructions": [
        "How should Circuit OS handle the failure in the case?",
        "Under the retry policy, what is the correct response to the failure described in the case?",
        "Pick the handling that the X5 policy prescribes for the case.",
        "According to the policy, which response does the failure in the case get?",
    ],
    "options": {
        "no_retry_503": "The failure is an API error from the model provider (outage, overload, authentication or rate limit): no retry, HTTP 503.",
        "no_retry_422": "The forced tool_use input fails the IntentIR schema: no retry, HTTP 422 with the raw tool input.",
        "retry_once": "The input is schema-valid, a generator envelope refused it, and one retry could add a missing value without changing what the user asked.",
        "refuse_out_of_catalogue": "The request is outside the catalogue: no generator could ever cover it, so it is refused without retry.",
        NMI: NMI_DESC,
    },
    "prop": "the policy's response to the case is {L}",
    "negprop": "the policy's response to the case is something other than {L}",
}

# ---------------------------------------------------------------- ROUTE: generator routing
FAMILIES["ROUTE"] = {
    "source": "handoff 2026-09-25 section 5 (five generators = entire catalogue; free-form out of scope); CLAUDE.md TPL_001-005",
    "context": [
        "Circuit OS generator catalogue (the entire catalogue; free-form circuits are out of scope). Boards: arduino_uno, esp32_devkitc, blackpill_f411ce.\n"
        "- rc_lowpass (TPL_004): a passive RC low-pass filter; the user gives a cutoff frequency.\n"
        "- voltage_divider (TPL_005): a two-resistor divider from a supply voltage to a lower target voltage.\n"
        "- led_indicator (TPL_003): an MCU GPIO pin driving an LED through a current-limiting resistor.\n"
        "- dht22_node (TPL_001): an MCU reading a DHT22 temperature and humidity sensor, with an alert threshold.\n"
        "- rs485_node (TPL_002): an MCU with a MAX485 transceiver acting as a Modbus RTU master on RS-485.\n"
        "Any request that none of these five covers is refused as out of catalogue.",
        "The five generators below are everything Circuit OS can build; it does not design free-form circuits. Supported boards are arduino_uno, esp32_devkitc and blackpill_f411ce.\n"
        "rc_lowpass (TPL_004) builds a passive low-pass filter from a resistor and a capacitor for a requested cutoff frequency. "
        "voltage_divider (TPL_005) builds a pair of resistors that divides a supply down to a lower target voltage. "
        "led_indicator (TPL_003) builds an LED driven from a microcontroller GPIO pin through a current-limiting resistor. "
        "dht22_node (TPL_001) builds a microcontroller that reads a DHT22 temperature/humidity sensor and alerts past a threshold. "
        "rs485_node (TPL_002) builds a microcontroller plus MAX485 transceiver working as a Modbus RTU master on an RS-485 bus. "
        "A request not covered by one of these five is refused as outside the catalogue.",
        "Catalogue (complete - nothing outside it is generated):\n"
        "| generator | template | builds |\n"
        "| rc_lowpass | TPL_004 | passive RC low-pass filter for a given cutoff frequency |\n"
        "| voltage_divider | TPL_005 | two resistors dividing a supply to a lower target voltage |\n"
        "| led_indicator | TPL_003 | LED on an MCU GPIO pin with a current-limiting resistor |\n"
        "| dht22_node | TPL_001 | MCU reading a DHT22 temperature/humidity sensor with an alert threshold |\n"
        "| rs485_node | TPL_002 | MCU + MAX485 transceiver as a Modbus RTU master on RS-485 |\n"
        "Boards: arduino_uno, esp32_devkitc, blackpill_f411ce. Requests outside the five are refused (out of catalogue).",
        "Circuit OS has exactly five generators and refuses anything else as out of catalogue; free-form circuits are not supported. The boards it targets are arduino_uno, esp32_devkitc and blackpill_f411ce. "
        "For a filter made of a resistor and a capacitor with a chosen cutoff, it uses rc_lowpass (TPL_004). To step a supply voltage down to a lower target with two resistors, it uses voltage_divider (TPL_005). "
        "For a light-emitting diode on a microcontroller pin with a resistor limiting its current, it uses led_indicator (TPL_003). For a microcontroller reading a DHT22 temperature and humidity sensor and raising an alert past a threshold, it uses dht22_node (TPL_001). "
        "For a microcontroller with a MAX485 transceiver acting as Modbus RTU master over RS-485, it uses rs485_node (TPL_002).",
    ],
    "instructions": [
        "Which generator should handle the user's request?",
        "Route the request in the case to the catalogue entry that covers it.",
        "Given the catalogue, which generator (or refusal) fits the user's request?",
        "Which catalogue entry does the user's request belong to?",
    ],
    "options": {
        "rc_lowpass": "A passive RC low-pass filter for a requested cutoff frequency.",
        "voltage_divider": "A two-resistor divider from a supply voltage to a lower target voltage.",
        "led_indicator": "An LED driven from an MCU GPIO pin through a current-limiting resistor.",
        "dht22_node": "An MCU reading a DHT22 temperature and humidity sensor with an alert threshold.",
        "rs485_node": "An MCU with a MAX485 transceiver acting as a Modbus RTU master on RS-485.",
        "refuse_out_of_catalogue": "None of the five generators covers the request.",
        NMI: NMI_DESC,
    },
    "prop": "the user's request should be handled by {L}",
    "negprop": "the user's request should be handled by something other than {L}",
}

# ---------------------------------------------------------------- OWN: one owner per fact
FAMILIES["OWN"] = {
    "source": "p2/.claude/shared-memory/AGENTS.md 'ONE OWNER PER FACT' table",
    "context": [
        "Circuit OS rule: one owner per fact (.claude/shared-memory/AGENTS.md). Each fact has exactly one owner file; everywhere else links to it.\n"
        "- Phase 1 criteria and their status: owned by tools/regen_state.py (PHASE1_CRITERIA), which generates state.json.\n"
        "- Test counts, verified percentage, module status: owned by progress.yaml and state.json (derived by regen_state.py; never edited by hand).\n"
        "- The 5-phase roadmap: owned by PRODUCT_MASTER.md.\n"
        "- This session's tasks: owned by plan/current_phase.md.\n"
        "- Why a choice was made: owned by brain/decisions.md.\n"
        "- The project file tree: owned by .claude/CLAUDE.md.",
    ],
    "instructions": [
        "Which file owns the fact in the case?",
        "Under the one-owner rule, where must the fact described in the case be written?",
        "Under 'one owner per fact', which file is the owner of this fact?",
        "Which owner file should hold the fact the agent wants to record?",
    ],
    "options": {
        "regen_state_py": "tools/regen_state.py (PHASE1_CRITERIA): Phase 1 criteria and their status.",
        "progress_yaml_state_json": "progress.yaml and state.json (derived): test counts, verified percentage, module status.",
        "product_master_md": "PRODUCT_MASTER.md: the 5-phase roadmap.",
        "current_phase_md": "plan/current_phase.md: this session's tasks.",
        "decisions_md": "brain/decisions.md: why a choice was made.",
        "claude_md": ".claude/CLAUDE.md: the project file tree.",
        NMI: NMI_DESC,
    },
    "prop": "the fact in the case is owned by {L}",
    "negprop": "the fact in the case is owned by a file other than {L}",
}

# ---------------------------------------------------------------- TRUST: trust hierarchy
FAMILIES["TRUST"] = {
    "source": "p2/.claude/shared-memory/AGENTS.md 'TRUST HIERARCHY'",
    "context": [
        "Circuit OS trust hierarchy (AGENTS.md). When sources disagree, the higher one wins:\n"
        "1. Test results and simulation outputs (highest)\n"
        "2. Source code via ast scan\n"
        "3. progress.yaml and state.json\n"
        "4. plan/current_phase.md\n"
        "5. brain/*.md files\n"
        "6. Agent-written prose summaries (lowest)",
        "When two Circuit OS sources contradict each other, AGENTS.md says the one ranked higher is believed. From most to least trusted: test results and simulation outputs; then the source code as seen by an ast scan; then progress.yaml and state.json; then plan/current_phase.md; then the brain/*.md files; and last, prose summaries written by agents.",
        "Ranking used to settle disagreements between sources (AGENTS.md), highest first:\n"
        "- rank 1: what tests and simulations actually output\n"
        "- rank 2: the source code, read through an ast scan\n"
        "- rank 3: the derived files progress.yaml and state.json\n"
        "- rank 4: the planner's plan/current_phase.md\n"
        "- rank 5: the hand-written brain/*.md notes\n"
        "- rank 6: prose summaries that agents wrote\n"
        "The higher-ranked source wins.",
        "AGENTS.md orders the project's sources by trust so conflicts can be settled mechanically: reality first (test results and simulation outputs), then code (source code via ast scan), then the files derived from those two (progress.yaml and state.json), then the planner's intent (plan/current_phase.md), then the brain/*.md hints, and finally agent-written prose summaries, which rank lowest. Whichever conflicting source sits higher in this order is the one to believe.",
    ],
    "instructions": [
        "Which source should be believed?",
        "The two sources in the case disagree; which one wins?",
        "Under the trust hierarchy, whose account prevails in the case?",
        "Which of the conflicting sources in the case should the agent trust?",
    ],
    "options": {  # labels are per item (the two sources named in the case)
        NMI: NMI_DESC,
    },
    "prop": "the source that should be believed is {L}",
    "negprop": "the source that should be believed is not {L}",
}

# ---------------------------------------------------------------- PATCH: patch rules
FAMILIES["PATCH"] = {
    "source": "p2 decisions.md [2026-09-21] X2 + X4 accepted; handoff section 2 (Patches); api/routes/patch.py 409 version_conflict",
    "context": [
        "Circuit OS patch rules (amendments X2 and X4; backend/api/routes/patch.py, backend/ai/intent_patcher.py).\n"
        "- A patch is an RFC 6902 operation list over IntentIR.requirements. It edits the requirement, never the circuit: a path into CircuitIR (components, nets, values) is rejected.\n"
        "- Every operation written by the LLM patcher must cite, verbatim, words from the user's command, and those words must contain the value written. An uncited operation is rejected.\n"
        "- A patch submitted against a version other than the design's current version is rejected with 409 version_conflict.\n"
        "- A patch whose operations leave the requirements unchanged is not a new version: it returns the same design unchanged.\n"
        "- Otherwise the patched requirement is re-derived through the same envelope() -> generate() -> predict() gate and accepted as the next revision.\n"
        "- Patches are never retried.",
        "How Circuit OS handles a patch (X2/X4; backend/api/routes/patch.py and backend/ai/intent_patcher.py): a patch is a list of RFC 6902 operations applied to IntentIR.requirements, so it changes the requirement and never the circuit itself; any operation whose path points into CircuitIR (its components, nets or values) is rejected. "
        "Each operation produced by the LLM patcher has to quote words from the user's command verbatim, and the quoted words must contain the value being written; an operation without such a citation is rejected. "
        "If the patch names a version that is not the design's current one, it is rejected with 409 version_conflict. "
        "If applying the operations leaves the requirements exactly as they were, no new version is created and the same design comes back unchanged. "
        "Any other patch is re-derived through the usual envelope() -> generate() -> predict() gate and becomes the next revision. No patch is ever retried.",
        "Patch handling, step by step (X2/X4):\n"
        "1. Path check: operations may only touch IntentIR.requirements; an operation on a CircuitIR path (components, nets, values) -> rejected (edits the circuit).\n"
        "2. Citation check: each LLM-written operation must quote the user's command verbatim, and the quote must contain the written value; otherwise -> rejected (uncited).\n"
        "3. Version check: the patch must target the design's current version; otherwise -> 409 version_conflict.\n"
        "4. No-op check: if the requirements end up unchanged -> no new version; the same design is returned.\n"
        "5. Otherwise -> re-derived through envelope() -> generate() -> predict() and accepted as the next revision.\n"
        "Patches are never retried.",
        "In Circuit OS a patch never edits the circuit: it is an RFC 6902 list of operations over IntentIR.requirements, and an operation aimed at a CircuitIR path such as a component, net or value is rejected. "
        "Operations from the LLM patcher are only valid when they cite the user's own words verbatim and those words include the value being set; uncited operations are rejected. "
        "A patch aimed at any version other than the current one fails with 409 version_conflict. "
        "A patch that ends up changing nothing in the requirements does not create a version; the unchanged design is returned. "
        "Everything else passes through the same envelope() -> generate() -> predict() gate as a fresh request and is accepted as the next revision. Patches get no retries.",
    ],
    "instructions": [
        "What happens to the patch in the case?",
        "Under the patch rules, what is the outcome for this patch?",
        "Classify the patch described in the case according to the rules.",
        "Which outcome do the patch rules give for the submitted patch?",
    ],
    "options": {
        "accept": "The patch edits IntentIR.requirements, every operation is cited, it targets the current version and it changes something: accepted as the next revision.",
        "reject_edits_circuit": "An operation's path points into CircuitIR (components, nets, values) instead of IntentIR.requirements.",
        "reject_uncited": "An operation does not cite the user's command verbatim with the written value.",
        "reject_version_conflict_409": "The patch targets a version other than the design's current version.",
        "noop_not_a_version": "The operations leave the requirements unchanged, so no new version is created.",
        NMI: NMI_DESC,
    },
    "prop": "the outcome for the patch in the case is {L}",
    "negprop": "the outcome for the patch in the case is something other than {L}",
}

# ---------------------------------------------------------------- SCOPE: phase scope
FAMILIES["SCOPE"] = {
    "source": "handoff 2026-09-25 sections 2, 8, 9; CLAUDE.md Phase 1 exclusions and PCB note",
    "context": [
        "Circuit OS scope as of Phase 2 (branch phase2-stage0; owner handoff 2026-09-25).\n"
        "In scope now: the Validation Engine and Stage 6 - BOM with static pricing and part substitution (GET /design/{id}/bom, BOMTable, price_asof on every price), the five catalogue generators, assurance claims and proofs, multi-MCU firmware for arduino_uno, esp32_devkitc and blackpill_f411ce.\n"
        "Out of Phase 2 (Phase 3 or later): switching converters, PCB layout (the custom A* router is experimental and must not be extended; Phase 3 will integrate freerouting), Gerber/DFM/fab APIs, foreign-netlist recognition, fine-tuning, team features.\n"
        "Needs the owner's explicit approval before any work: live pricing (X7: Digikey/LCSC live API).",
        "What Circuit OS may work on right now (Phase 2, branch phase2-stage0, per the owner's 2026-09-25 handoff): the Validation Engine and Stage 6, meaning the BOM with static prices and part substitution (the GET /design/{id}/bom route, the BOMTable view, and a price_asof on each price); the five generators in the catalogue; assurance claims and proofs; and firmware for arduino_uno, esp32_devkitc and blackpill_f411ce. "
        "Deferred to Phase 3 or later: switching converters; PCB layout (the experimental custom A* router is not to be extended, since Phase 3 will bring in freerouting); Gerber, DFM and fab APIs; recognising foreign netlists; fine-tuning; and team features. "
        "Live pricing through the Digikey or LCSC API (X7) may not be started without the owner's explicit approval.",
        "Scope table (Phase 2, phase2-stage0, handoff 2026-09-25)\n"
        "NOW: Validation Engine; Stage 6 BOM with static pricing and substitution (GET /design/{id}/bom, BOMTable, price_asof per price); the five catalogue generators; assurance claims and proofs; firmware for arduino_uno / esp32_devkitc / blackpill_f411ce.\n"
        "LATER (Phase 3+): switching converters; PCB layout (custom A* router is experimental - do not extend it; freerouting comes in Phase 3); Gerber / DFM / fab APIs; foreign-netlist recognition; fine-tuning; team features.\n"
        "OWNER APPROVAL FIRST: live pricing via the Digikey/LCSC API (X7).",
        "Per the owner's handoff of 2026-09-25, Phase 2 work on phase2-stage0 covers the Validation Engine and Stage 6 (a BOM priced statically, with part substitution, a GET /design/{id}/bom endpoint, a BOMTable component and a price_asof beside every price), plus the five catalogue generators, the assurance claims and proofs, and firmware for the three supported boards. "
        "Switching converters, PCB layout, Gerber/DFM/fab APIs, foreign-netlist recognition, fine-tuning and team features all belong to Phase 3 or later; in particular the experimental custom A* router must not be extended because Phase 3 will use freerouting. "
        "Live pricing from Digikey or LCSC (X7) is a special case: it requires the owner's explicit approval before anyone starts on it.",
    ],
    "instructions": [
        "How should the proposed work in the case be classified?",
        "Is the proposal in the case in scope now, out of scope, or does it need the owner's approval?",
        "Classify the proposed work in the case against the current scope.",
        "Where does the proposal in the case fall relative to the current scope?",
    ],
    "options": {
        "in_scope_now": "The work is part of the current Phase 2 scope.",
        "out_of_scope_later_phase": "The work belongs to Phase 3 or later (or must not be extended now).",
        "needs_owner_approval": "The work needs the owner's explicit approval before it starts.",
        NMI: NMI_DESC,
    },
    "prop": "the proposal in the case is {L}",
    "negprop": "the proposal in the case is not {L}",
}

# ---------------------------------------------------------------- RULE: critical rules
FAMILIES["RULE"] = {
    "source": "CLAUDE.md 'Critical Rules - Never Violate' 1-8",
    "context": [
        "Circuit OS critical rules (CLAUDE.md), never to be violated:\n"
        "one_rule: LLM output -> JSON -> IR schema -> deterministic compilers. The LLM never writes SPICE, KiCad or firmware directly.\n"
        "celery: simulation always runs via Celery, never inline in an HTTP handler.\n"
        "mcu_resistor: the MCU SPICE model is a resistor (100 ohm on the Uno), never a voltage source.\n"
        "columnar_output: ngspice batch output is columnar; the regex v(x) = y does not match it.\n"
        "kicanvas_ssr: kicanvas is loaded with a dynamic import and ssr: false; it is never server-rendered.\n"
        "postgres: all designs persist to PostgreSQL; no in-memory design_store = {}.\n"
        "cors_first: CORS middleware is added before any route is registered.\n"
        "static_bom: BOM pricing is static; no live Digikey/LCSC API calls.",
        "The rules Circuit OS must never break (from CLAUDE.md):\n"
        "one_rule - the LLM produces JSON that is validated against the IR schema and then compiled deterministically; it never writes SPICE, KiCad or firmware itself.\n"
        "celery - every simulation goes through Celery; none runs inside an HTTP handler.\n"
        "mcu_resistor - in SPICE the microcontroller is a resistor (100 ohm for the Uno), not a voltage source.\n"
        "columnar_output - ngspice's batch output comes in columns, so a v(x) = y regex cannot parse it.\n"
        "kicanvas_ssr - kicanvas must be imported dynamically with ssr: false and never rendered on the server.\n"
        "postgres - designs are stored in PostgreSQL, never in an in-memory design_store = {} dict.\n"
        "cors_first - the CORS middleware goes in before any route is registered.\n"
        "static_bom - BOM prices are static; the live Digikey/LCSC APIs are not called.",
        "Critical rules (CLAUDE.md). Rule id: requirement.\n"
        "- one_rule: LLM -> JSON -> IR schema -> compilers; never LLM -> SPICE/KiCad/firmware.\n"
        "- celery: simulations run as Celery jobs; never inline in an HTTP handler.\n"
        "- mcu_resistor: MCU in SPICE = resistor (100 ohm, Uno); never a voltage source.\n"
        "- columnar_output: ngspice batch output is columnar; `v(x) = y` regexes do not match it.\n"
        "- kicanvas_ssr: kicanvas via dynamic import with ssr: false; never SSR.\n"
        "- postgres: all designs persist to PostgreSQL; no in-memory store.\n"
        "- cors_first: CORS middleware before any route.\n"
        "- static_bom: static BOM pricing; no live Digikey/LCSC calls.",
        "CLAUDE.md lists eight rules that no change may violate. Under one_rule, anything an LLM outputs must pass as JSON through the IR schema to deterministic compilers, so an LLM never writes SPICE, KiCad or firmware directly. "
        "Under celery, simulations are always Celery jobs and never run inline inside an HTTP handler. Under mcu_resistor, the microcontroller is modelled in SPICE as a resistor (100 ohm for the Uno) and never as a voltage source. "
        "Under columnar_output, code must respect that ngspice batch output is columnar, which a v(x) = y regex does not match. Under kicanvas_ssr, kicanvas is loaded through a dynamic import with ssr: false and never rendered server-side. "
        "Under postgres, every design is persisted to PostgreSQL rather than kept in an in-memory design_store = {}. Under cors_first, CORS middleware is added before any route is registered. Under static_bom, BOM pricing stays static with no live Digikey or LCSC API calls.",
    ],
    "instructions": [
        "Which critical rule, if any, does the proposal in the case violate?",
        "Does the proposal in the case break one of the critical rules? If so, which one?",
        "Name the critical rule the proposal violates, or say that it complies.",
        "Check the proposal in the case against the critical rules: which one does it break, if any?",
    ],
    "options": {
        "one_rule": "The proposal lets LLM output reach SPICE, KiCad or firmware without the JSON -> IR -> compiler path.",
        "celery": "The proposal runs a simulation inline in an HTTP handler instead of via Celery.",
        "mcu_resistor": "The proposal models the MCU in SPICE as a voltage source instead of a resistor.",
        "columnar_output": "The proposal parses ngspice batch output as if it were v(x) = y lines.",
        "kicanvas_ssr": "The proposal server-renders kicanvas or imports it without dynamic import and ssr: false.",
        "postgres": "The proposal keeps designs in memory instead of persisting them to PostgreSQL.",
        "cors_first": "The proposal registers routes before adding the CORS middleware.",
        "static_bom": "The proposal calls a live Digikey/LCSC pricing API.",
        "complies": "The proposal violates none of the critical rules.",
        NMI: NMI_DESC,
    },
    "prop": "the proposal in the case violates the rule {L}",
    "negprop": "the proposal in the case does not violate the rule {L}",
}
