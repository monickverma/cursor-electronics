"""items_judgment.py - Circuit OS judgment items (no ground truth; consistency metrics only).

J01-J06: short owner/agent decisions written from the p2 snapshot and the 2026-09-25 handoff,
each with 3 hand-written state paraphrases (context + case) and shared instruction paraphrases.
RJ01-RJ08: the 8 governing Choices of the committed requests in tools/jev/requests/ (loaded
verbatim at build time; not paraphrased).
PJ: judgment polarity pairs built on those request states (x and a hand-written negation).
"""
from items_spec import NMI, NMI_DESC

J_INSTRUCTIONS = [
    "Which option should be chosen for the decision in the case?",
    "Given the facts, what is the best choice for the decision described in the case?",
    "Pick the option that the facts in the state best support for this decision.",
    "Which of the options is the right call for the decision in the case?",
]

J = []


def jitem(**kw):
    J.append(kw)


jitem(id="J01", topic="first D1 bench generator",
      options={"rc_lowpass_first": "Bench-check the rc_lowpass generator's claims first.",
               "led_indicator_first": "Bench-check the led_indicator generator's claims first.",
               "voltage_divider_first": "Bench-check the voltage_divider generator's claims first.",
               NMI: NMI_DESC},
      context=[
          "D1 bench session planning (docs/BENCH_D1.md; owner handoff 2026-09-25). The owner has no oscilloscope and no function generator; a multimeter and a bench supply are available. One generator's claims will be checked on the bench first.\n"
          "rc_lowpass 0.2.3: its key claim is the AC cutoff frequency; measuring it needs a function generator and an oscilloscope.\n"
          "led_indicator 0.2.0: its key claims are LED current and exact dissipation (Task 4.5); both are DC and measurable with a multimeter. The bench sheet still names version 0.1.1.\n"
          "voltage_divider 0.1.0: its key claim is the DC output voltage; measurable with a multimeter; the simplest generator, with the fewest parts.\n"
          "The evidence-record code that stores a bench result against a claim has been decided but not built.",
          "Planning the first D1 bench session (per docs/BENCH_D1.md and the 2026-09-25 handoff): the owner owns a multimeter and a bench power supply but neither an oscilloscope nor a function generator, and only one generator will be bench-checked first. "
          "For rc_lowpass 0.2.3 the central claim is its AC cutoff frequency, which cannot be measured without a function generator and an oscilloscope. "
          "For led_indicator 0.2.0 the central claims are the LED current and its exact dissipation from Task 4.5; both are DC quantities a multimeter can measure, though the bench sheet still refers to version 0.1.1. "
          "For voltage_divider 0.1.0 the central claim is a DC output voltage, again measurable with a multimeter; it is the simplest generator and uses the fewest parts. "
          "How a bench result will be recorded against a claim (the evidence-record code) has been decided but not yet written.",
          "First D1 bench session - inputs:\n"
          "* Equipment on hand: multimeter, bench supply. Missing: oscilloscope, function generator.\n"
          "* Only one generator gets bench-checked first.\n"
          "* rc_lowpass 0.2.3 - main claim: AC cutoff frequency - needs function generator + oscilloscope.\n"
          "* led_indicator 0.2.0 - main claims: LED current, exact dissipation (Task 4.5) - DC, multimeter is enough - bench sheet still says 0.1.1.\n"
          "* voltage_divider 0.1.0 - main claim: DC output voltage - multimeter is enough - simplest generator, fewest parts.\n"
          "* Evidence-record code (bench result -> claim): decided, not built.\n"
          "Sources: docs/BENCH_D1.md, owner handoff 2026-09-25.",
          "Only one generator can be checked in the first D1 bench session, and the owner has just a multimeter and a bench supply - no oscilloscope, no function generator (docs/BENCH_D1.md; handoff of 2026-09-25). "
          "Checking rc_lowpass 0.2.3 means measuring its AC cutoff frequency, which requires exactly the two instruments the owner lacks. "
          "Checking led_indicator 0.2.0 means measuring LED current and the exact dissipation added in Task 4.5, both DC and within a multimeter's reach; its bench sheet is out of date and names 0.1.1. "
          "Checking voltage_divider 0.1.0 means measuring one DC output voltage with a multimeter; it is the simplest generator with the fewest parts. "
          "The code for recording a bench result as evidence against a claim is decided but unbuilt.",
      ],
      case=["Decision: which generator should the first D1 bench session check?",
            "Decision to make: the generator whose claims the first D1 bench session checks.",
            "Decision: pick the generator for the first D1 bench session.",
            "Decision: for the first D1 bench session, which generator's claims come first?"])

jitem(id="J02", topic="criterion 12 cold-read timing",
      options={"before_first_prospect_demo": "Schedule the criterion 12 cold read before the first prospect demo.",
               "at_phase3_kickoff": "Schedule the criterion 12 cold read when Phase 3 starts.",
               "keep_deferred_until_first_user": "Keep it deferred until the first external user is shown an explanation.",
               NMI: NMI_DESC},
      context=[
          "Criterion 12 (an external engineer reads a generated explanation cold) is deferred with the trigger 'before the first external user is shown an explanation' (decisions.md, 2026-08-25). Defeater D3 stays open until the review is done. "
          "The Phase 3 KPI is a first enterprise contract, and a demo to a prospect is being considered for next month. The review costs about two hours of one engineer's time plus the owner's preparation (CRITERION_12_REVIEW.md). No reviewer has been recruited yet.",
          "The criterion 12 review - an outside engineer reading a generated explanation without a briefing - was deferred on 2026-08-25 (decisions.md), to be done 'before the first external user is shown an explanation', and D3 remains open until then. "
          "Phase 3 is measured by landing a first enterprise contract; a prospect demo is under consideration for next month. According to CRITERION_12_REVIEW.md the review takes roughly two hours of one engineer plus preparation by the owner. Nobody has yet been recruited as reviewer.",
          "Criterion 12 status:\n"
          "- What: an external engineer reads a generated explanation cold.\n"
          "- Deferred 2026-08-25 (decisions.md); trigger: before the first external user is shown an explanation.\n"
          "- Defeater D3 open until done.\n"
          "- Cost: ~2 h of one engineer + owner prep (CRITERION_12_REVIEW.md).\n"
          "- Reviewer: none recruited.\n"
          "Context: Phase 3 KPI = first enterprise contract; a prospect demo is being considered for next month.",
          "No reviewer has been found yet for criterion 12, under which an engineer from outside reads a generated explanation cold; per CRITERION_12_REVIEW.md this takes about two hours of that engineer's time and some preparation from the owner. "
          "It was deferred on 2026-08-25 (decisions.md) with the trigger 'before the first external user is shown an explanation', and until it happens defeater D3 stays open. "
          "Meanwhile the Phase 3 KPI is the first enterprise contract, and a demo for a prospect may happen next month.",
      ],
      case=["Decision: when should the criterion 12 cold read be scheduled?",
            "Decision to make: the timing of the criterion 12 cold read.",
            "Decision: choose when to run the criterion 12 cold read.",
            "Decision: at what point should the criterion 12 cold read take place?"])

jitem(id="J03", topic="CI branch triggers",
      options={"add_phase2_stage0_only": "Add phase2-stage0 to the CI triggers and keep the rest.",
               "trigger_on_all_branches": "Run CI on pushes to every branch.",
               "keep_current_triggers": "Leave the CI triggers as they are.",
               NMI: NMI_DESC},
      context=[
          "CI (.github/workflows/ci.yml) runs on pushes to main, master and develop and on pull requests to main and master. All work since Phase 1 is on phase2-stage0, which has never been merged, so CI has never run on it. "
          "CI installs arduino-cli, but Stage 5 compiles firmware with PlatformIO 6.2.0. A full CI run takes about 12 minutes; the owner is the only committer.",
          "The workflow in .github/workflows/ci.yml fires on pushes to main, master and develop, and on pull requests into main and master. Since Phase 1 every commit has gone to phase2-stage0, a branch never merged, so CI has not once run on that work. "
          "The workflow sets up arduino-cli even though Stage 5 builds firmware with PlatformIO 6.2.0. One CI run lasts about 12 minutes, and only the owner commits.",
          "CI facts:\n"
          "- Triggers: push to main / master / develop; PR to main / master (.github/workflows/ci.yml).\n"
          "- Active branch: phase2-stage0 (all work since Phase 1, never merged) -> CI has never run on it.\n"
          "- Toolchain mismatch: CI installs arduino-cli; Stage 5 compiles with PlatformIO 6.2.0.\n"
          "- Run time ~12 min. Committers: the owner only.",
          "Only the owner commits, and every commit since Phase 1 is on phase2-stage0, which has never been merged; because .github/workflows/ci.yml triggers only on pushes to main, master or develop and on pull requests to main or master, CI has never run on any of it. "
          "The workflow also installs arduino-cli, while Stage 5 compiles firmware with PlatformIO 6.2.0. A complete run takes roughly 12 minutes.",
      ],
      case=["Decision: how should the CI triggers change?",
            "Decision to make: what to do with the CI triggers.",
            "Decision: choose the new CI trigger configuration.",
            "Decision: should the CI triggers be changed, and how?"])

jitem(id="J04", topic="commit convention",
      options={"conventional_everywhere": "Enforce conventional commits (feat:, fix:, docs:) for every commit.",
               "session_prefix_everywhere": "Enforce 'session: <description>' for every commit.",
               "conventional_plus_session_for_handoffs": "Conventional commits, except 'session:' for end-of-session handoff commits.",
               NMI: NMI_DESC},
      context=[
          "The owner's handoff says commits are conventional (feat:, fix:, docs:). AGENTS.md's session handoff tells agents to commit 'session: <brief description>'. The /update-memory command writes 'brain:' commits. Recent history mixes all three. A regex check can enforce whichever convention is chosen.",
          "Three commit conventions coexist: the owner's handoff calls for conventional commits (feat:, fix:, docs:), the session handoff in AGENTS.md asks agents for 'session: <brief description>', and the /update-memory command produces 'brain:' commits. The recent log contains all three styles. Any one of them could be enforced with a regex check.",
          "Commit message conventions in play:\n"
          "1. Owner handoff: conventional commits (feat:, fix:, docs:).\n"
          "2. AGENTS.md session handoff: 'session: <brief description>'.\n"
          "3. /update-memory command: 'brain:' prefix.\n"
          "Recent history: a mix of all three. Enforcement: a regex check can enforce the chosen one.",
          "Recent commits mix three styles because three sources disagree: /update-memory writes 'brain:' commits, AGENTS.md's session handoff says to commit 'session: <brief description>', and the owner's handoff says commits are conventional (feat:, fix:, docs:). Whichever is chosen can be enforced by a regex check.",
      ],
      case=["Decision: which commit-message convention should be enforced?",
            "Decision to make: the commit-message convention to enforce.",
            "Decision: pick the commit convention the regex check will enforce.",
            "Decision: which convention should commit messages follow from now on?"])

jitem(id="J05", topic="first Phase 3 industrial class",
      options={"dcv_controller_first": "Build the DCV (demand-controlled ventilation) controller first.",
               "pump_controller_first": "Build the pump controller first.",
               "sensor_gateway_first": "Build the sensor gateway first.",
               NMI: NMI_DESC},
      context=[
          "Phase 3 targets industrial controller boards. Candidate first classes: (a) DCV (demand-controlled ventilation) controller: needs a 24 VAC to 3.3 V switching supply, and switching converters are outside Phase 2 scope; "
          "(b) pump controller: needs a relay driver and motor-contact sensing, and no generator exists for either; (c) sensor gateway: RS-485 Modbus plus temperature/humidity sensing; rs485_node and dht22_node already exist. PRODUCT_MASTER.md lists the DCV controller first.",
          "The first industrial controller class for Phase 3 has three candidates. A DCV (demand-controlled ventilation) controller would need a switching supply from 24 VAC to 3.3 V, and switching converters were kept out of Phase 2. "
          "A pump controller would need a relay driver and sensing of motor contacts, neither of which has a generator. A sensor gateway would combine RS-485 Modbus with temperature and humidity sensing, for which rs485_node and dht22_node already exist. The DCV controller is the first class listed in PRODUCT_MASTER.md.",
          "Phase 3 first-class candidates (industrial controller boards):\n"
          "| class | needs | existing generators |\n"
          "| DCV controller | 24 VAC -> 3.3 V switching supply (switching converters out of Phase 2 scope) | none for the supply |\n"
          "| pump controller | relay driver, motor-contact sensing | none |\n"
          "| sensor gateway | RS-485 Modbus, temperature/humidity sensing | rs485_node, dht22_node |\n"
          "PRODUCT_MASTER.md lists the DCV controller first.",
          "PRODUCT_MASTER.md names the DCV (demand-controlled ventilation) controller as the first Phase 3 industrial class, but it depends on a 24 VAC to 3.3 V switching supply, and switching converters were outside Phase 2 scope. "
          "The alternatives are a pump controller, which requires a relay driver and motor-contact sensing with no generator for either, and a sensor gateway, which needs RS-485 Modbus and temperature/humidity sensing that rs485_node and dht22_node already provide.",
      ],
      case=["Decision: which industrial class should Phase 3 build first?",
            "Decision to make: the first industrial class for Phase 3.",
            "Decision: choose the Phase 3 industrial class to build first.",
            "Decision: which class should be Phase 3's first build?"])

jitem(id="J06", topic="unregistered backend modules",
      options={"register_all_now": "Register all seven files in MODULES now.",
               "register_with_allowlist_for_exclusions": "Register them, with an allowlist that names any intentional exclusions and why.",
               "leave_as_is": "Leave MODULES unchanged.",
               NMI: NMI_DESC},
      context=[
          "Seven backend files are absent from MODULES in tools/regen_state.py: ai/openai_compat.py, core/ir_examples.py, data/component_constraints.py, db/models.py, main.py, middleware/rate_limit.py and worker.py. "
          "AGENTS.md says an unregistered module does not show up as untested - it does not show up at all - and a wrong denominator looks like health. Registering them lowers the reported verified percentage. Some of the files (entry points, configuration) may be excluded on purpose.",
          "tools/regen_state.py's MODULES list omits seven backend files: ai/openai_compat.py, core/ir_examples.py, data/component_constraints.py, db/models.py, main.py, middleware/rate_limit.py and worker.py. "
          "Per AGENTS.md, a module that is not registered is invisible rather than reported as untested, and an incorrect denominator masquerades as health. Adding these files would reduce the verified percentage that is reported. A few of them, such as entry points or configuration, might be left out deliberately.",
          "Unregistered backend files (not in MODULES, tools/regen_state.py): ai/openai_compat.py; core/ir_examples.py; data/component_constraints.py; db/models.py; main.py; middleware/rate_limit.py; worker.py.\n"
          "AGENTS.md: an unregistered module does not appear at all; a wrong denominator looks like health.\n"
          "Effect of registering: the reported verified % goes down.\n"
          "Caveat: some (entry points, configuration) may be excluded intentionally.",
          "Registering ai/openai_compat.py, core/ir_examples.py, data/component_constraints.py, db/models.py, main.py, middleware/rate_limit.py and worker.py - the seven backend files missing from MODULES in tools/regen_state.py - would lower the verified percentage the project reports. "
          "AGENTS.md warns that a module left unregistered simply disappears from the report and that a wrong denominator looks like health. Some of these files, being entry points or configuration, may have been left out on purpose.",
      ],
      case=["Decision: what should be done about the unregistered backend files?",
            "Decision to make: how to handle the seven unregistered backend files.",
            "Decision: choose what to do with the backend files missing from MODULES.",
            "Decision: should the unregistered backend files be registered, and how?"])

JUDG = J

# Request-judgment items: (item id, request file, governing question name)
RJ = [
    ("RJ01", "rs485_de_re_pulldown.json", "pulldown_option"),
    ("RJ02", "x7_live_pricing.json", "x7_option"),
    ("RJ03", "d1_bench_timing.json", "d1_when"),
    ("RJ04", "proof_kind_label.json", "kind_option"),
    ("RJ05", "explainer_budget.json", "first_step"),
    ("RJ06", "stage6_finish.json", "kpi_5pct_disposition"),
    ("RJ07", "stage6_finish.json", "stage6_finish_before_phase3"),
    ("RJ08", "accuracy_flake_policy.json", "flake_policy"),
]

# Judgment polarity pairs on request states: x (as in the request, or new) and a hand-written
# negation. truth_x: only where the state itself settles it (None otherwise).
PJ = [
    dict(id="PJ1", request="rs485_de_re_pulldown.json",
         x="For a single-master Modbus RTU node on a bench or small bus, is a driver briefly enabled during MCU reset a material risk to other nodes' communication?",
         notx="For a single-master Modbus RTU node on a bench or small bus, is a driver briefly enabled during MCU reset negligible for other nodes' communication?",
         truth_x=None),
    dict(id="PJ2", request="rs485_de_re_pulldown.json",
         x="Given the state, would adding the pull-down remove the reason D2 (simplified MCU model) is cited on the fail-safe claim, rather than just moving it to another claim?",
         notx="Given the state, would adding the pull-down leave the D2 (simplified MCU model) citation in place, or merely move it to another claim, rather than remove it?",
         truth_x=None),
    dict(id="PJ3", request="x7_live_pricing.json",
         x="Does any stated Stage 6 gate require a live price rather than a dated static one?",
         notx="Can every stated Stage 6 gate be met with a dated static price, without a live price?",
         truth_x=False, derivation="x7 state fact: 'Static exact-match pricing with price_asof 2026-07-25 already meets the Stage 6 price gates.'"),
    dict(id="PJ4", request="x7_live_pricing.json",
         x="Does the state contain the vendor's caching/display terms and rate limit?",
         notx="Are the vendor's caching/display terms and rate limit missing from the state?",
         truth_x=False, derivation="x7 state fact: 'vendor caching/display terms, key handling, rate limits and cost are unknown.'"),
    dict(id="PJ5", request="proof_kind_label.json",
         x="Is v2's empirical tag for z3-proved claims a considered classification rather than a drafting slip?",
         notx="Is v2's empirical tag for z3-proved claims a drafting slip rather than a considered classification?",
         truth_x=None),
    dict(id="PJ6", request="proof_kind_label.json",
         x="May a lower-precedence document's definition override v2's field value without amending v2?",
         notx="Must v2 be amended before a lower-precedence document's definition can override v2's field value?",
         truth_x=None),
    dict(id="PJ7", request="proof_kind_label.json",
         x="Would an external engineer read 'analytic' as 'validated on hardware'?",
         notx="Would an external engineer understand that 'analytic' does not mean 'validated on hardware'?",
         truth_x=None),
    dict(id="PJ8", request="explainer_budget.json",
         x="Would raising max_tokens alone bring generation under 15 s?",
         notx="Would generation still take 15 s or more if max_tokens were raised and nothing else changed?",
         truth_x=None),
]
