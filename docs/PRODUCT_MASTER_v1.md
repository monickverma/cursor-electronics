> # SUPERSEDED — archived 2026-08-22
>
> This is `PRODUCT_MASTER.md` **version 1.0**, the original pre-build product
> definition. It is kept for history and is **not** the spec to build from.
>
> The canonical spec is `PRODUCT_MASTER.md` at the repo root. It revised this
> document in two ways that were deliberate and are still in force:
>
> | | This file (v1) | Canonical |
> |---|---|---|
> | Phase 3 | "KiCad Workflow Layer" — freerouting, Gerber, fab APIs, DFM, industrial bundled together | "Industrial Layer" — DCV, refrigeration, RS-485, UL 508A. Gerber/DFM/fab moved to Phase 4 |
> | Pro tier | $29/month | $49/month |
>
> The Phase 3 change moved the industrial vertical **earlier** and the
> manufacturing workflow **later**, on the argument in `MENTAL_MODEL.md` §9 that
> industrial rule libraries are the one area no competitor occupies.
>
> Confirmed canonical on 2026-08-22 — see `brain/decisions.md`.
>
> Do not build from this file. Read it only to understand why something is the
> way it is.

---

# CIRCUIT OS — Complete Product Definition
### The AI Hardware Compiler: From Natural Language to Manufacturable Electronics

---

## PART 1 — WHAT YOU ARE BUILDING

### The One-Sentence Definition

> A software platform that turns a plain English hardware description into a complete, validated, simulation-tested, manufacture-ready electronics design — including the circuit, the firmware, the bill of materials, and the safety analysis — before a single physical component is touched.

### The One-Paragraph Definition

You are building the GCC of physical hardware. Just as a software compiler takes high-level human-readable code and produces machine-executable binary, your system takes a high-level human-readable hardware intent and produces a physically executable design. The engineer describes what they want. Your software decides how to build it, validates that it works using physics simulation, catches every mistake it can find, and hands back a folder of files ready to send to a manufacturer. No other tool on the market does all of this in a single workflow.

### What It Is Not

- It is not a chatbot that talks about electronics
- It is not a smarter Google for datasheets
- It is not a drawing tool with AI autocomplete (that is Flux.ai)
- It is not a simulation tool (that is standalone ngspice or LTspice)
- It is not a PCB layout tool (that is standalone KiCad)

It is all of those things connected together under a single intelligence layer that understands intent.

---

## PART 2 — THE COMPLETE USER JOURNEY

This is what a user actually experiences, from first prompt to physical board in hand.

### Step 1 — The Prompt

The user types a plain English description of what they want to build. No technical knowledge required to get started. Examples at different complexity levels:

**Beginner level:**
"I want to turn on an LED when it gets dark."

**Intermediate level:**
"Build a temperature monitoring system for a warehouse that alerts when temperature exceeds 40°C."

**Professional level:**
"Design a DIN-rail mounted RTU that reads 8 Modbus RTU devices on RS-485, samples every 30 seconds, buffers data locally, and transmits to an MQTT broker over LTE-M cellular. Power from 24VDC."

All three prompts go through the same system. The output scales in complexity accordingly.

### Step 2 — Intent Parsing

The system reads the prompt and extracts structured meaning. It identifies:
- What the device needs to do (the function)
- What constraints exist (voltage, current, power budget, form factor, environment)
- What communication protocols are involved
- What safety requirements apply
- What the target application is (hobbyist, industrial, safety-critical)

If the prompt is ambiguous, the system asks the single most important clarifying question before proceeding. It does not ask five questions. It asks one.

### Step 3 — Design Generation

The system selects circuit topology, chooses specific components, assigns pin connections, calculates values, and writes the complete design into a structured intermediate representation (the IR — explained fully in Part 4). This is where all the intelligence happens:

- It chose the DHT22 over the DS18B20. It explains why.
- It chose a buck converter over a linear regulator. It explains why.
- It chose the STM32 over the ESP32. It explains why.
- Every single decision is logged with a confidence score and a justification.

### Step 4 — Simulation

The design is automatically compiled to a SPICE netlist and sent to ngspice (running as a subprocess). The simulation runs in the background — typically 2–15 seconds. The post-processor reads the results and grades them:

- Did the output voltage hit the target? (DC operating point check)
- Is the filter cutoff within 10% of the specified frequency? (AC sweep check)
- Does the transient response settle within acceptable time? (Transient analysis)
- Is the power dissipation within component ratings? (Thermal check)

Simulation is the physics truth. Not the AI's opinion. If simulation says a component will overheat, the system automatically swaps it for a better-rated alternative and re-simulates.

### Step 5 — Validation

Beyond simulation, the rule engine runs a structured set of checks specific to the design type:

- Wrong voltage level on a microcontroller pin
- Missing pull-up resistor on I2C or open-drain lines
- Invalid pin assignment (PWM function on non-PWM pin)
- Unsupported or end-of-life component
- Missing current limiting resistor on LED
- Insufficient decoupling capacitance on power rail
- Incorrect TVS diode clamping voltage on RS-485 lines
- Missing termination resistor on long RS-485 runs
- Optoisolation missing on industrial I/O

Each violation produces a plain English explanation, not an error code.
❌ Instead of: "ERC Error: unconnected pin on U1"
✅ You get: "The data pin on your DHT22 is floating. Add a 10kΩ pull-up resistor from this pin to 3.3V or the sensor will not respond."

### Step 6 — The Output Package

When the system finishes, the user receives a complete design package:

**The Schematic (.kicad_sch)**
A professional wiring diagram that opens directly in KiCad. Every component placed, every connection made, every net labeled. Ready for manual review and modification.

**The Simulation Report**
Graphs showing voltage waveforms, frequency response, or current profiles depending on the circuit type. A pass/fail summary with numerical results. Confidence level for each check.

**The Bill of Materials (.csv)**
Every component with: manufacturer part number, Digikey part number, LCSC part number, unit price, total cost, availability (in-stock quantity), package size, and a one-line description. Sortable and ready to submit to a distributor.

**The Firmware**
For Arduino, ESP32, and STM32 targets: working, commented source code. Not boilerplate. The actual logic for the described application — reading the sensor, checking the threshold, triggering the output, implementing the communication protocol. Ready to flash.

**The Validation Report (.pdf)**
A structured document listing every check that ran, every pass, every warning, every failure, and the reasoning behind each. This is what an engineer shows their manager or client as proof the design was reviewed.

**The PCB Layout (.kicad_pcb) — Phase 2+**
A preliminary board layout with components placed and initial routing. Ready for manual review and finishing in KiCad. Includes DRC results and a DFM (Design for Manufacturability) note flagging any features that will add cost at fabrication.

**Gerber Files — Phase 2+**
The manufacturing-ready files. Exportable directly to JLCPCB, PCBWay, or OSHPark for fabrication. From English sentence to board order in one session.

### Step 7 — Iterative Editing (The Cursor-Level Feature)

After the initial design is generated, the user can continue the conversation and modify the design incrementally. This is what separates the product from every other AI electronics tool:

The system does NOT regenerate from scratch. It patches the existing design.

User: "Make it run on battery instead of USB."
System: Adds a LiPo charge circuit (TP4056), adds a boost converter if needed, changes the power supply section, recalculates current consumption, recalculates battery life, re-runs simulation on the affected sections only, reports the impact.

User: "Use a cheaper sensor."
System: Queries the component database filtered by function and price, selects an alternative, updates the component, checks that the new pinout and protocol match the existing firmware, patches the firmware if needed, re-validates.

User: "This needs to work in a -40°C environment."
System: Checks the operating temperature range of every selected component, flags the ones that fail the spec, substitutes industrial-grade alternatives, adjusts component ratings, re-validates.

---

## PART 3 — EVERYTHING THE PRODUCT CAN BUILD (COMPLETE USE CASE SCOPE)

### Tier 1 — MVP (Months 1–3)

**Arduino digital circuits.** The system handles any circuit that involves a microcontroller, digital sensors, and basic output control. Specific circuits supported at launch:

- RC low-pass and high-pass filters
- Voltage dividers
- LED driver circuits with current limiting
- Arduino + temperature sensor (DHT22, DS18B20, LM35)
- Arduino + humidity sensor
- Arduino + motion sensor (PIR)
- Arduino + relay control
- Arduino + LCD/OLED display
- Basic transistor switch circuits

### Tier 2 — Phase 2 (Months 3–8)

**IoT and connected systems.** The system expands to ESP32-based designs, WiFi connectivity, and basic power management:

- ESP32 WiFi sensor nodes
- Battery-powered IoT devices with sleep modes and calculated battery life
- 4–20mA analog input conditioning circuits
- UART and I2C multi-sensor designs
- Simple relay control boards
- Motor driver circuits (DC motor with L298N, stepper with A4988/DRV8825)
- Power supply circuits (5V buck, 3.3V LDO, 12V→5V step-down)
- USB-C power delivery circuits

### Tier 3 — Phase 3 (Months 8–18)

**Industrial and HVAC control.** This is where the product becomes enterprise-grade:

**Demand Controlled Ventilation (DCV) boards:**
CO2 sensor interface (SCD30/SCD41 over I2C, or Telaire 6004 analog), microcontroller PID control loop, 0–10V analog output circuit driving a VFD, relay output for damper actuator, RS-485 Modbus RTU transceiver for BMS communication, 24VAC-to-3.3V power supply, fail-safe logic (defaults to maximum ventilation if sensor fails). The system generates the circuit, the PID firmware, and calculates energy savings.

**Commercial Kitchen Hood Controllers:**
Variable speed exhaust fan control via 0–10V VFD signal, makeup air fan balancing, duct temperature sensor input for fire detection, UV sensor input for flame presence, dry contact inputs from Ansul fire suppression system, relay outputs for gas valve shutoff and equipment lockout, human interface with alarm display. The system flags UL 508A requirements and life-safety design rules.

**Advanced Refrigeration Control:**
NTC thermistor and PT100/PT1000 RTD temperature inputs, 4–20mA pressure transducer inputs (suction and discharge), relay outputs for compressor staging and defrost heaters, stepper motor H-bridge driver for Electronic Expansion Valve (EEV) control using DRV8825, RS-485 Modbus for rack controller integration, demand-based defrost logic, superheat calculation firmware.

**PLC-Style Control Boards:**
24VDC digital inputs with optoisolation (PC817), relay or transistor digital outputs, 4–20mA analog inputs and outputs, RS-485 Modbus RTU slave interface, watchdog circuit, hardened power supply for industrial environments. Firmware generated as structured text logic or C with deterministic timing.

### Tier 4 — Phase 4 (Months 18+)

**SCADA and Remote Telemetry (RTU boards):**
This is the most complete use case and the most compelling enterprise product. A full remote telemetry unit designed entirely by the system:

Hardware the system generates:
- Microcontroller section (STM32F4 or ESP32)
- RS-485 Modbus RTU master interface (MAX485/SP3485, TVS protection, termination, bias resistors)
- Cellular modem section (SIM7070G for LTE-M/NB-IoT, SIM card holder, antenna connector, power decoupling for 2A transmit spike)
- 24VDC industrial power input with buck converter (TPS54360), 3.3V LDO, separate modem power path
- 4–20mA analog inputs with INA219 receiver circuits
- Optoisolated digital inputs
- Terminal blocks, status LEDs, debug header

Firmware the system generates:
- Modbus RTU master polling up to 247 slave devices
- JSON payload packaging
- AT command cellular transmission (TCP/MQTT)
- Local flash buffer for cellular outage periods
- Watchdog timer
- Low-power sleep scheduling

Data pipeline the system specifies (not builds, but defines):
- API endpoint contract the board posts to
- TimescaleDB or InfluxDB schema for the data
- Grafana dashboard configuration

This is the full path: English sentence → designed board → manufactured board → live data on a dashboard. No existing tool provides this end-to-end.

---

## PART 4 — THE TECHNICAL ARCHITECTURE (COMPLETE)

### The Fundamental Rule

**The LLM never writes netlists, SPICE syntax, or KiCad files directly.** All LLM output is JSON. The JSON is validated against a schema. The schema is deterministically compiled to all downstream formats. This single rule is what separates a reliable engineering tool from an AI toy that hallucinates circuit values.

### Layer 1 — UI Layer

Web application (Next.js), VS Code extension (Phase 2), CLI (Phase 2), REST API (Phase 1 for enterprise integrations).

UI components:
- Chat interface for prompt input and conversational editing
- Schematic canvas using kicanvas (browser-native KiCad renderer, open source)
- Simulation waveform viewer (Plotly.js)
- BOM panel with live pricing and availability
- Design history timeline (version browser)
- Validation report panel

### Layer 2 — AI Brain

Three sub-modules, all communicating via structured JSON:

**Intent Parser:** Receives the raw user prompt. Uses Claude or GPT-4 with function calling to extract a structured design spec: application type, functional requirements, constraints (voltage, current, environment, budget, form factor), communication protocols required, safety classification. Output is a DesignSpec JSON object, not free text.

**Circuit Reasoner:** Receives the DesignSpec. Selects circuit topology from the topology library (RC filter, buck converter, H-bridge, optoisolated input, RS-485 transceiver, etc.). Calculates component values. Selects specific parts from the component database. Builds the full Intermediate Representation (IR). Every decision is tagged with a confidence score.

**Explanation Engine:** Reads the IR and generates plain English explanations for every component choice, every topology decision, every warning. This output goes directly to the user. It is the most important differentiator in the product — the reasoning that makes engineers trust the system.

**RAG System:** A vector database (Qdrant or pgvector) containing manufacturer datasheets, application notes, IEC/UL standards excerpts, and known circuit patterns. The Circuit Reasoner queries this during design generation to ground its decisions in actual documentation.

### Layer 3 — The Intermediate Representation (IR)

This is the core innovation. The canonical JSON schema that all other layers read and write. The single source of truth for any design in the system.

```json
{
  "circuit_id": "uuid-v4",
  "version": 3,
  "intent": "Modbus RTU master with LTE-M cellular telemetry, 24VDC input",
  "application_class": "industrial_iot",
  "safety_class": "general",

  "components": [
    {
      "id": "U1",
      "type": "microcontroller",
      "part": "STM32F405RGT6",
      "manufacturer": "STMicroelectronics",
      "digikey_pn": "497-15960-ND",
      "lcsc_pn": "C8832",
      "package": "LQFP-64",
      "supply_voltage": 3.3,
      "confidence": 0.91,
      "justification": "Selected for hardware UART multiplexing (2 UARTs needed: Modbus + modem), FreeRTOS support, and industrial temp range -40 to 85°C"
    }
  ],

  "nodes": [
    { "id": "VCC_3V3", "voltage_nominal": 3.3, "type": "power" },
    { "id": "VCC_5V",  "voltage_nominal": 5.0, "type": "power" },
    { "id": "GND",     "voltage_nominal": 0,   "type": "ground" },
    { "id": "MODBUS_A","type": "signal", "protocol": "RS485_differential" },
    { "id": "MODBUS_B","type": "signal", "protocol": "RS485_differential" }
  ],

  "connections": [
    { "component": "U1", "pin": "PA9",  "node": "UART1_TX" },
    { "component": "U1", "pin": "PA10", "node": "UART1_RX" }
  ],

  "constraints": {
    "supply_voltage_input": 24,
    "operating_temp_min": -40,
    "operating_temp_max": 85,
    "certifications_required": ["CE", "RoHS"],
    "modbus_slave_count_max": 32,
    "cellular_protocol": "LTE-M"
  },

  "simulation_spec": {
    "analyses": [
      { "type": "dc_op",      "description": "Verify all rail voltages" },
      { "type": "transient",  "stop_time": "0.1", "description": "Power-on sequencing" }
    ]
  },

  "validation_rules": [
    "no_floating_nodes",
    "voltage_ratings_ok",
    "rs485_termination_present",
    "rs485_bias_resistors_present",
    "modem_decoupling_sufficient",
    "watchdog_present",
    "industrial_temp_range_all_components"
  ],

  "patch_history": [
    { "version": 2, "change": "Swapped LM7805 linear reg for TPS54360 buck (thermal)", "timestamp": "2025-01-15T14:23:00Z" }
  ]
}
```

The IR is then compiled by four independent compilers:
- **IR → SPICE netlist** (for ngspice simulation)
- **IR → .kicad_sch** (for schematic viewing and editing)
- **IR → Firmware** (C/Arduino/.ino source code)
- **IR → BOM spreadsheet** (with live Digikey/LCSC pricing)

### Layer 4 — Tool Execution Layer

All tools run as subprocesses or CLI calls from the Python backend. No GUI required.

**KiCad (headless):** Called via KiCad CLI. Generates .kicad_sch from the IR. Runs ERC and returns structured results. In Phase 2, generates .kicad_pcb with auto-placement. In Phase 3, exports Gerber files, drill files, pick-and-place files.

**ngspice (subprocess):** Receives SPICE netlist. Runs the analysis types specified in the IR's simulation_spec. Returns raw data in tabular format. The post-processor parses this, extracts key metrics, compares against the IR's constraints, generates pass/fail grades.

**Post-processor:** Analyzes simulation output. Identifies anomalies — unexpected oscillation, voltage overshoot, thermal limit approach, insufficient settling time. Feeds results back to the AI Brain for re-evaluation if any check fails.

**Firmware generator:** Templates + IR data → compilable source code. Uses Jinja2 templating for Arduino/C. For Phase 3+, generates IEC 61131-3 structured text for PLC-style applications.

### Layer 5 — Data Layer

**PostgreSQL:** User accounts, projects, design history, team memberships, audit logs.

**Circuit Pattern Vector DB (Qdrant):** Every generated design is stored as an embedding. When a new design starts, the system retrieves the 5 most similar previous designs as context. This is what makes the system smarter over time — it has seen this problem before.

**Component Database (PostgreSQL + nightly sync):** Full component catalog with specs, footprints, ratings, pricing, availability. Synced nightly from Digikey V3 API and LCSC API. Never call the distributor API live — always query local cache.

**Simulation Cache (Redis):** Identical simulation runs (same netlist) return cached results instantly. Prevents unnecessary compute for common circuits.

**Training Flywheel Pipeline:** Every design → simulation → validation cycle generates labeled data. "This circuit worked" / "This circuit had a short" / "This component needed a pull-up." With user consent, this data feeds a fine-tuning pipeline that improves the Circuit Reasoner over time. This is the compounding competitive advantage.

### The Diff-and-Patch Edit System

When a user edits an existing design conversationally, the system does NOT regenerate. It patches.

The edit prompt to the LLM includes: the full current IR + the user's edit command. The LLM is instructed to return only a `patch` object specifying changed fields, not a full new IR. The patch is validated against the IR schema. Only changed components are re-simulated. Unchanged sections are preserved exactly.

This means: user customizations survive edits. Design history is preserved. The system behaves like a version-controlled design tool, not a generative toy.

---

## PART 5 — MVP: WHAT TO BUILD IN 12 WEEKS

### What the MVP Accepts
A single natural language prompt describing an Arduino-compatible hardware intent. One board. Digital circuits only. No analog power electronics. No multi-board systems. No file uploads.

### What the MVP Produces (In This Order)
1. Component list with justification for each choice
2. Wiring diagram as a .kicad_sch file, viewable in browser via kicanvas
3. Arduino .ino firmware, commented and ready to flash
4. Validation report with pass/fail on five specific checks
5. Plain English explanation of every design decision

### The Five MVP Validation Checks
1. Wrong voltage level on a microcontroller pin
2. Missing pull-up resistor on I2C, 1-Wire, or open-drain signal lines
3. Invalid pin assignment (e.g., PWM function requested on non-PWM-capable pin)
4. Unsupported or end-of-life component selected
5. Obvious wiring error caught by KiCad ERC

### The Five Supported Circuit Templates (MVP Only)
1. RC low-pass filter (calculated cutoff, standard values)
2. RC high-pass filter
3. Voltage divider with load analysis
4. LED driver with current limiting resistor
5. Arduino + digital sensor (DHT22, PIR, ultrasonic — 3 sensor variants)

These are templates, not free generation. The LLM fills in values and constraints against a validated schema. This produces reliable, non-hallucinated output. Free generation expands in Phase 2 once the template system has proven reliability.

### Week-by-Week Build Plan

**Weeks 1–3: Physics engine first.**
Build the IR schema. Build the ngspice subprocess wrapper (pyspice). Prove that a manually written IR compiles correctly to a SPICE netlist, runs, and returns parsed data. The AI is not involved yet. This foundation must be solid.

**Weeks 4–6: LLM → IR translator.**
Build the prompt-to-IR translation for the five templates. Use Claude function calling with the IR schema as the output schema. Build the retry loop (if JSON fails schema validation, re-prompt with the error). Test with 20 different prompt phrasings per template.

**Weeks 7–8: Validation and explanation layer.**
Post-simulation, grade the output. Generate the plain English explanation chain. This is the feature that makes engineers trust the system — build it carefully.

**Weeks 9–10: Chat interface and KiCad integration.**
Next.js frontend with chat panel and kicanvas schematic viewer. KiCad CLI headless schematic generation from IR. Add the edit/patch capability.

**Weeks 11–12: Component validation layer.**
For every component in the IR, check voltage rating against supply voltage, check datasheet requirements (pull-up needed? specific capacitor dielectric?), surface warnings in plain language with specific resistor values and part suggestions.

### What Does NOT Exist in MVP
PCB layout, BOM pricing API, Gerber export, team collaboration, simulation waveform graphs (text-only pass/fail), analog circuits, generative free-form design, enterprise features, mobile app.

---

## PART 6 — FULL 5-PHASE ROADMAP

### Phase 1 — "Hardware Copilot" (Months 0–3)
Target users: Arduino hobbyists, CS/EE students, indie makers.
Deliverables: 5 circuit templates, ngspice validation, ERC checks, Arduino code generation, plain English explanation layer.
KPIs: Circuit generation under 30 seconds. Simulation accuracy ≥85% match to bench measurement. 100 beta users. At least 3 documented "it caught my mistake" testimonials.
Revenue: Free.

### Phase 2 — "Validation Engine" (Months 3–8)
Target users: Serious makers, IoT startup teams, freelance hardware engineers.
Deliverables:
- Free-form circuit generation (beyond 5 templates)
- KiCad schematic export with clean layout
- ESP32 and STM32 target support
- BOM with live Digikey/LCSC pricing and availability
- Diff-and-patch iterative editing
- Component substitution engine ("find a cheaper/more available alternative")
- Basic analog circuits: op-amp configurations, buck/boost converters, LDO regulators
- Simulation waveform viewer
- Design version history with timeline UI

KPIs: 3 paying pilot teams. Average design time under 45 minutes for a complete IoT node. BOM accuracy within 5% of manual engineer's component selection.
Revenue: Pro tier at $29/month.

### Phase 3 — "KiCad Workflow Layer" (Months 8–18)
Target users: Hardware product teams, contract electronics engineers, HVAC controls companies.
Deliverables:
- PCB auto-routing via KiCad freerouting integration
- Gerber export and direct fab API integration (JLCPCB, PCBWay)
- DFM (Design for Manufacturability) report generation
- Industrial circuit support: RS-485, 4–20mA, 24VDC power, optoisolation
- DCV board generation (full demand-controlled ventilation design)
- Commercial refrigeration control board generation
- Private component libraries (organization-scoped)
- Design diff viewer and rollback
- Team workspace with role-based access

KPIs: First enterprise contract signed. At least one customer goes from prompt to ordered PCB within one working day.
Revenue: Team tier at $99/seat/month.

### Phase 4 — "Enterprise Platform" (Months 18–30)
Target users: OEMs, industrial automation companies, HVAC manufacturers, building automation vendors.
Deliverables:
- Full SCADA/RTU board generation (Modbus RTU master + cellular)
- PLC-style control board generation
- Hood controller board generation
- SSO and enterprise identity management
- Audit trail meeting ISO 13485 and ISO 26262 documentation requirements
- Compliance reporting (UL, CE, RoHS flag generation)
- ROI dashboard ("time saved vs manual baseline" per engineer)
- API access for integration into existing engineering workflows
- Fine-tuned domain model trained on accumulated design data

KPIs: $1M ARR. Average 40% reduction in prototype cycle time documented by enterprise customers.
Revenue: Enterprise contracts, custom pricing.

### Phase 5 — "Advanced Hardware Intelligence" (Months 30+)
Target users: High-complexity engineering teams, advanced power electronics, RF.
Deliverables:
- Thermal simulation integration (for power dissipation and junction temperature analysis)
- Analog power electronics: full switching power supply design, battery management systems
- Multi-objective optimization: "minimize cost, minimize size, maximize reliability" with Pareto front
- BOM cost optimization across multiple distributors
- Reliability prediction (MTBF estimation based on component ratings and stress)
- Full data pipeline generation (board → firmware → cloud schema → dashboard specification)

---

## PART 7 — TECHNOLOGY STACK

### Backend
- **Python 3.11+** — primary language throughout
- **FastAPI** — REST API layer, async throughout
- **Celery + Redis** — async job queue for simulation runs (never block the API thread)
- **PostgreSQL** — primary database (projects, users, components, audit logs)
- **Qdrant** — vector database for circuit pattern similarity search
- **pyspice** — Python wrapper for ngspice subprocess
- **KiCad CLI** — headless schematic and PCB generation via subprocess
- **Pydantic v2** — IR schema validation (strict mode, no extra fields allowed)
- **Jinja2** — firmware code templating

### AI/ML
- **Claude API (claude-sonnet-4-6)** — primary LLM, used with tool_use/function_calling to enforce JSON output
- **Anthropic tool use** — forces IR-schema-compliant output, eliminates free-text hallucination
- **pgvector or Qdrant** — RAG retrieval for datasheet and application note context

### Frontend
- **Next.js 14** — web application
- **kicanvas** — browser-native KiCad schematic renderer (open source, no KiCad install required)
- **Plotly.js** — simulation waveform visualization
- **Tailwind CSS** — styling

### External APIs
- **Digikey V3 API** — component pricing and availability (cached nightly, never called live)
- **LCSC API** — low-cost component alternative pricing
- **JLCPCB API (Phase 2+)** — Gerber submission and order tracking
- **PCBWay API (Phase 2+)** — alternative fabrication option

### Infrastructure
- **Docker + Docker Compose** — containerized services
- **AWS or GCP** — cloud hosting
- **GitHub Actions** — CI/CD
- **Sentry** — error tracking
- **PostHog** — product analytics (track time-from-prompt-to-valid-design as primary KPI)

---

## PART 8 — COMPETITIVE POSITION

### The Landscape

| Tool | What It Is | What It Cannot Do |
|---|---|---|
| Flux.ai | Cloud PCB editor with basic AI autocomplete | Does not understand intent. No simulation loop. No firmware. |
| Altium 365 | Enterprise PCB design platform | Manual design only. No AI reasoning. $500+/month. |
| Cadence Allegro | Professional EDA suite | Extremely complex. No AI. No intent-based design. |
| Celus.io | Automated schematic entry for automotive OEMs | Closed, expensive, no simulation loop, no firmware. |
| ChatGPT / Claude | General LLM | Will hallucinate circuit values. No simulation. No files. |

### Your Defensible Position

"The only tool that closes the complete loop: natural language intent → simulation-validated circuit → compiled firmware → manufacture-ready files → iterative editing."

No competitor does all five. That is the wedge.

### The Moat (What Becomes Harder to Copy Over Time)

1. **Circuit pattern vector database** — grows with every user design, enables better similarity search and context
2. **Labeled simulation outcomes** — "this circuit passed / this one had a short / this one needed a pull-up" — training data no competitor can buy
3. **Fine-tuned domain model** — trained specifically on electronics design, not general text
4. **Component pricing intelligence** — accumulated knowledge of what's available, at what price, with what lead time
5. **Industry-specific rule libraries** — HVAC rules, refrigeration rules, industrial I/O rules, safety rules — each one built from engineering expertise and user feedback

---

## PART 9 — BUSINESS MODEL

### Pricing Tiers

**Free:** 50 generations per month, 5 simulation runs, community component library, no export, no version history. Purpose: acquire hobbyists and students, build the circuit pattern database.

**Pro — $29/month:** Unlimited generations, unlimited simulation, BOM with live pricing, KiCad export, Gerber export (Phase 2+), version history, 5 projects. Target: freelance engineers, serious makers, IoT startup founders.

**Team — $99/seat/month:** Everything in Pro, private component libraries, team workspace, design review workflow, audit trail, priority support, API access. Minimum 3 seats. Target: small hardware product companies, engineering consultancies.

**Enterprise — Custom:** Everything in Team, SSO/SAML, compliance reporting, dedicated fine-tuning on company data, SLA, on-premise option for IP-sensitive customers, ROI reporting dashboard. Target: OEMs, HVAC manufacturers, industrial automation companies.

### What Companies Actually Pay For

Not circuit generation. They pay for:
- Engineering time saved (measurable: log time-from-prompt-to-valid-design)
- Mistakes caught before boards are ordered (measurable: ERC/DRC catch rate)
- Junior engineer productivity (measurable: output quality per engineer-hour)
- Prototype cycle reduction (measurable: sprints from prompt to working board)

The ROI dashboard built into the Team/Enterprise tier surfaces these numbers automatically. That is the renewal conversation.

---

## PART 10 — KEY TECHNICAL DECISIONS AND RATIONALE

**Why ngspice instead of LTspice?**
LTspice is owned by Analog Devices. Its EULA explicitly prohibits commercial redistribution and server-side automation. You cannot legally call LTspice in a SaaS product without a licensing agreement that Analog Devices does not grant easily. ngspice is fully open-source (BSD license), SPICE-compatible, scriptable via subprocess, and KiCad has built-in ngspice integration. Use ngspice from day one.

**Why the IR must be strict JSON schema (no free text)?**
LLMs hallucinate. They will invent resistor values that don't exist in standard series, specify capacitor voltages below the supply rail, write SPICE syntax that ngspice cannot parse. The IR schema enforces physical constraints at the data layer. If the LLM outputs a capacitor with a 3V rating in a 5V circuit, schema validation rejects it before it reaches the simulation. The retry loop re-prompts with the specific violation. This is the only reliable way to produce correct circuits at scale.

**Why simulation must be the truth, not the LLM's opinion?**
A language model has no internal physics engine. It has statistical associations between words. It knows "capacitor" appears near "filter" in its training data, but it does not simulate electron flow. Simulation runs actual SPICE equations. When simulation says the output voltage is 4.8V not 5V, that is a physics result, not a prediction. The system trusts simulation, not the LLM, for any numerical claim about circuit behavior.

**Why diff-and-patch editing instead of regeneration?**
If the system regenerates the entire IR on every edit, user customizations are lost. An engineer might manually override a component choice, adjust a pin assignment to match their board constraints, or add a comment to a net. Regeneration destroys all of that. The patch model applies changes surgically, preserves everything not explicitly modified, and maintains a complete change history. This is the behavior engineers expect from a professional tool.

**Why start with Arduino/digital and not jump straight to industrial?**
Arduino circuits are deterministic and forgiving. Component values can be off by 20% and the circuit still works. This makes it possible to prove the system works and build user trust before tackling analog circuits where parasitics, layout sensitivity, and noise make simulation accuracy much harder. The hobbyist market also provides volume — thousands of users generating thousands of designs — which builds the circuit pattern database and training flywheel faster than targeting 50 industrial customers first.

---

## PART 11 — WHAT THIS BECOMES

### Short Term (Year 1)
An AI assistant for electronics that hobbyists and indie engineers use to build faster. The market sees it as "ChatGPT for circuits." Revenue comes from Pro subscriptions. Value is speed and error-catching.

### Medium Term (Year 2–3)
A hardware prototyping platform that engineering teams use as their primary design environment. The market sees it as "Cursor for hardware." Revenue comes from Team and early Enterprise contracts. Value is workflow integration and team productivity.

### Long Term (Year 3+)
The standard interface for hardware design. The GCC of physical electronics. Any engineer at any level — from a student building their first sensor to a controls engineer designing an industrial refrigeration rack — uses this as their starting point. The market sees it as a new category: Generative Electronic Design Automation (GEDA). Revenue comes from Enterprise contracts and platform fees. Value is the intelligence layer that no hardware company can afford not to have.

The markets this touches — HVAC controls, building automation, commercial refrigeration, industrial IoT, embedded systems, EV power electronics — collectively represent hundreds of billions of dollars in annual engineering services. The engineers doing that work today spend enormous amounts of time on the exact repetitive, mistake-prone design work this system automates.

---

## PART 12 — THE SINGLE MOST IMPORTANT THING

If everything in this document is reduced to one thing, it is this:

**The explanation layer is the product.**

Any engineer can run ngspice. Any engineer can open KiCad. What no tool in existence currently does is look at a circuit design and say, in plain English: "I chose this component for this reason. This is what will fail if you change it. This is what you need to check before ordering. Here is what I am not certain about and why."

That reasoning — applied to every component, every connection, every design decision — is what earns the trust of engineers who have been burned by automated tools before. It is what turns a junior engineer into a productive one. It is what a senior engineer shows their client as evidence the design was reviewed. It is what an enterprise buyer points to when justifying the seat license.

Build the explanation layer first. Build it carefully. Build it better than anything else in the product.

Everything else follows from trust.

---

*Document version 1.0 — synthesized from all design conversations, architecture sessions, and use case explorations. This is the complete product definition.*
