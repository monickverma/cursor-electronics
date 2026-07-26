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

**Intent Parser:** Receives the raw user prompt. Uses Claude with function calling to extract a structured design spec: application type, functional requirements, constraints (voltage, current, environment, budget, form factor), communication protocols required, safety classification. Output is a DesignSpec JSON object, not free text.

**Circuit Reasoner:** Receives the DesignSpec. Selects circuit topology from the topology library. Calculates component values. Selects specific parts from the component database. Builds the full Intermediate Representation (IR). Every decision is tagged with a confidence score.

**Explanation Engine:** Reads the IR and generates plain English explanations for every component choice, every topology decision, every warning. This output goes directly to the user. It is the most important differentiator in the product — the reasoning that makes engineers trust the system.

**RAG System (Phase 2+):** A vector database (Qdrant or pgvector) containing manufacturer datasheets, application notes, IEC/UL standards excerpts, and known circuit patterns. Phase 1 uses a static Python lookup table instead — zero tokens, zero latency, zero cost.

### Layer 3 — The Intermediate Representation (IR)

This is the core innovation. The canonical JSON schema that all other layers read and write. The single source of truth for any design in the system.

The IR is then compiled by four independent compilers:
- **IR → SPICE netlist** (for ngspice simulation)
- **IR → .kicad_sch** (for schematic viewing and editing)
- **IR → Firmware** (C/Arduino/.ino source code)
- **IR → BOM spreadsheet** (with live Digikey/LCSC pricing)

### Layer 4 — Tool Execution Layer

All tools run as subprocesses or CLI calls from the Python backend. No GUI required.

**ngspice (subprocess):** Receives SPICE netlist. Runs the analysis types specified in the IR's simulation_spec. Returns raw data in tabular format. The post-processor parses this, extracts key metrics, compares against the IR's constraints, generates pass/fail grades.

**Firmware generator:** Templates + IR data → compilable source code. Uses Jinja2 templating for Arduino/C.

### Layer 5 — Data Layer

**PostgreSQL:** User accounts, projects, design history, team memberships, audit logs.

**Component Constraints (Phase 1 — Python lookup table):** Static Python dict keyed by part number. Zero tokens, zero latency, zero cost. Injected selectively into the circuit reasoner prompt (200–500 tokens max, not 40,000+).

**Circuit Pattern Vector DB (Qdrant — Phase 2+):** Every generated design is stored as an embedding. When a new design starts, the system retrieves the 5 most similar previous designs as context.

**Component Database (PostgreSQL + nightly sync — Phase 2+):** Full component catalog with specs, footprints, ratings, pricing, availability. Synced nightly from Digikey V3 API and LCSC API. Never call the distributor API live.

**Simulation Cache (Redis):** Identical simulation runs (same netlist) return cached results instantly.

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
1. No floating nodes (every node has ≥2 connections)
2. Voltage rating ≥ supply voltage for every component
3. I2C buses have pull-up resistors on SDA and SCL
4. RS-485 buses have 120Ω termination resistor
5. PWM signals assigned to PWM-capable pins only

### The Five Supported Circuit Templates (MVP Only)
1. Arduino + DHT22 (temperature/humidity with threshold alert)
2. Arduino + MAX485 (RS-485 Modbus RTU master)
3. Arduino + LED with current-limiting resistor
4. RC low-pass filter (calculated cutoff)
5. Voltage divider (calculated output)

These are templates, not free generation. Free generation expands in Phase 2 once the template system has proven reliability.

### What Does NOT Exist in MVP
PCB layout, BOM pricing API, Gerber export, team collaboration, simulation waveform graphs (text-only pass/fail), analog circuits, generative free-form design, enterprise features, mobile app.

---

## PART 6 — FULL 5-PHASE ROADMAP

### Phase 1 — "Hardware Copilot" (Months 0–3)
Target users: Arduino hobbyists, CS/EE students, indie makers.
Deliverables: 5 circuit templates, ngspice validation, 5 rule checks, Arduino code generation, plain English explanation layer, KiCad export, diff-and-patch editing, static BOM, auth.
KPIs: Circuit generation under 30 seconds. Simulation accuracy ≥85% match to bench measurement. 100 beta users. At least 3 documented "it caught my mistake" testimonials.
Revenue: Free.

### Phase 2 — "Validation Engine" (Months 3–8)
Target users: Serious makers, IoT startup teams, freelance hardware engineers.
Deliverables:
- Free-form circuit generation (beyond 5 templates, 15 total)
- ESP32 and STM32 firmware support
- Live BOM pricing via Digikey/LCSC API (nightly cache sync)
- Design version history with timeline UI
- Qdrant RAG on 500 datasheet excerpts
- Simulation waveform viewer (Plotly.js)
- Component substitution engine

KPIs: 3 paying pilot teams. Average IoT node design under 45 minutes. BOM accuracy within 5%.
Revenue: Pro tier at $49/month.

### Phase 3 — "Industrial Layer" (Months 8–18)
Target users: HVAC controls companies, commercial kitchen equipment, refrigeration OEMs.
Deliverables:
- DCV board generation
- Commercial kitchen hood controller board generation
- Advanced refrigeration control
- RS-485 industrial I/O with optoisolation
- UL 508A flagging and safety class enforcement
- PCB auto-layout via KiCad freerouting (basic, 2–4 layer boards)
- Private component libraries per organization
- Audit trail (ISO 13485/26262 ready)

KPIs: First enterprise contract signed. One customer prompt-to-ordered-PCB within one business day.
Revenue: Team tier at $99/seat/month.

### Phase 4 — "Enterprise Platform" (Months 18–30)
Target users: OEMs, SCADA integrators, building automation vendors.
Deliverables:
- Full SCADA RTU board generation (Modbus RTU master + LTE-M cellular)
- PLC-style control board generation
- Gerber export + JLCPCB/PCBWay API integration
- DFM report
- SSO/SAML enterprise identity
- ROI dashboard
- Fine-tuned domain model on accumulated design data

KPIs: $1M ARR. Average 40% prototype cycle reduction documented.
Revenue: Enterprise contracts, custom pricing.

### Phase 5 — "Advanced Hardware Intelligence" (Months 30+)
Target users: High-complexity power electronics, RF, medical devices.
Deliverables:
- Thermal simulation (junction temperature analysis)
- Analog power electronics (full switching supply, BMS)
- Multi-objective BOM optimization (cost vs. size vs. reliability Pareto)
- MTBF prediction
- Full data pipeline generation (board → firmware → cloud schema → dashboard spec)

---

## PART 7 — TECHNOLOGY STACK

### Backend
- **Python 3.11+** — primary language throughout
- **FastAPI** — REST API layer, async throughout
- **Celery + Redis** — async job queue for simulation runs (never block the API thread)
- **PostgreSQL** — primary database (projects, users, components, audit logs)
- **ngspice** — physics simulation via subprocess (BSD licensed, legally usable in SaaS)
- **Pydantic v2** — IR schema validation (strict mode, no extra fields allowed)
- **Jinja2** — firmware code templating
- **slowapi** — rate limiting

### AI/ML
- **Claude API (claude-sonnet-4-6)** — primary LLM, used with tool_use/function_calling to enforce JSON output
- **Anthropic tool use** — forces IR-schema-compliant output, eliminates free-text hallucination
- **Qdrant (Phase 2+)** — RAG retrieval for datasheet and application note context

### Frontend
- **Next.js 14** — web application
- **kicanvas** — browser-native KiCad schematic renderer (open source, no KiCad install required, dynamic import with ssr:false)
- **Tailwind CSS** — styling

### External APIs
- **Digikey V3 API (Phase 2+)** — component pricing and availability (cached nightly, never called live)
- **LCSC API (Phase 2+)** — low-cost component alternative pricing
- **JLCPCB API (Phase 3+)** — Gerber submission and order tracking

### Infrastructure
- **Docker + Docker Compose** — containerized services
- **GitHub Actions** — CI/CD
- **Sentry** — error tracking
- **PostHog** — product analytics (track time-from-prompt-to-valid-design as primary KPI)

---

## PART 8 — COMPETITIVE POSITION (CORRECTED — Updated 2026)

### The Landscape

| Tool | What It Actually Does | Your Differentiation |
|---|---|---|
| **Flux.ai** | Natural language → PCB recommendations. 750K+ part library. Firmware assistance (pin mappings, init scripts). No integrated SPICE simulation (roadmap, not shipped). | You run physics simulation in the generation loop. You generate complete working firmware, not assistance. |
| **Celus.io** | High-level requirements → schematic with AI-assisted component selection. Validates compatibility against a database — not physics. No simulation, no firmware, no industrial rule libraries. Exports to your existing EDA tool. | You prove the parts work together with physics. You generate firmware. You own the industrial vertical they ignore. |
| **Quilter** | Takes a completed schematic (KiCad, Altium, Cadence) and produces a physics-validated PCB layout. Does not generate schematics. Does not take natural language input. No firmware. No simulation. | Not a competitor — a partner. Circuit OS generates the KiCad schematic; Quilter takes it for physics-optimized layout. |
| **Altium 365** | Enterprise PCB design platform. Manual design only. No AI reasoning. $500+/month. | No natural language input. No simulation loop. No firmware generation. |
| **ChatGPT / Claude** | General LLM | Will hallucinate circuit values. No simulation. No files. No validation. |

### Flux.ai — The Corrected, Detailed Assessment

Flux is a real competitor. Not a drawing tool with AI autocomplete. Their documentation (2026): "Copilot isn't operating in a vacuum — it's an AI agent with access to real tools, structured data, and your active design context including schematics, PCB, parts, netlist, and a 750K+ part library." They accept natural language, determine PCB layer count, recommend components, handle interoperability, suggest in-stock alternatives, and provide firmware assistance.

**Where Flux stops and Circuit OS starts:**
1. **Simulation:** Flux's own 2026 marketing lists simulation as a capability — it appears in their feature roadmap. Their platform today handles schematic generation, component placement, routing, and design rule checks. There is no integrated SPICE physics simulation in their technical documentation. It is on their roadmap. It is not built. That is your clearest differentiator.
2. **Firmware:** Flux provides firmware assistance — pin mappings, configuration files, initialization scripts based on netlist data. That is not a complete working `.ino` or `.c` file ready to flash. Circuit OS generates the actual code.
3. **Trust model:** Flux's own documentation advises: "treat it like a fast junior engineer: powerful, but you must review its work. We recommend intermediate PCB experience." Circuit OS simulates, validates, and explains why — so the review has evidence behind it, not just human intuition.

### Celus.io — The Corrected, Detailed Assessment

Celus overlaps with Circuit OS Tier 1 and 2. Their AI-assisted hardware design engine moves from high-level requirements to completed schematics. Their core value is component intelligence — matching specs against a database. Their "validated schematic" means component compatibility is checked, not physics.

**The differentiation from Celus is the physics layer and the industrial vertical.** Celus helps you pick the right parts. Circuit OS proves those parts work together correctly and tells you what will fail and why. Celus exports to your existing EDA tool rather than replacing the workflow. There is no firmware output, no SPICE simulation, no industrial rule libraries, no stateful editing.

### Quilter — The Corrected, Detailed Assessment

Quilter automates PCB placement and routing using physics-driven reinforcement learning. You upload a completed schematic and board file. Quilter understands circuit relationships and generates multiple candidate layouts with physics scorecards. It is genuinely world-class at one thing: taking a completed schematic and producing a physics-validated PCB layout.

**Quilter is not a competitor — it is a workflow partner.** Quilter supports KiCad native files. Circuit OS generates a KiCad schematic. A user takes the Circuit OS output and hands it to Quilter for physics-optimized layout. In Phase 3, Circuit OS adds basic auto-routing for 2–4 layer industrial control boards and recommends Quilter for high-complexity RF or high-speed digital boards.

### The Five Claims No Competitor Can Make

1. **Integrated SPICE physics simulation in the generation loop.** Not planned, not external, not mentioned in a roadmap. Running today. ngspice as part of the pipeline, auto-correcting component choices when simulation fails.
2. **Complete working firmware.** Not pin mappings, not initialization scripts, not firmware assistance. Working `.ino`, `.c`, Modbus RTU master code. Ready to flash.
3. **Stateful diff-and-patch editing.** Every other tool either regenerates or requires manual edit. The patch model preserves user customizations across edits. Design history is maintained.
4. **Consequential explanation.** Flux shows what it did. Circuit OS shows what will happen if the user changes something — with the simulation result as evidence. That distinction is what makes a senior engineer trust the output.
5. **Industrial and HVAC vertical.** Not a single competitor — Flux, Celus, Quilter, Altium — has RS-485 rule enforcement, 4–20mA circuit generation, DCV board templates, refrigeration control design, or SCADA/RTU board generation. This is the entire uncontested market.

### Corrected One-Sentence Position

**"The only AI hardware tool that simulates before it ships, explains why every decision was made, generates complete firmware, and serves the industrial controls market that every other AI tool ignores."**

### The Moat (What Becomes Harder to Copy Over Time)

1. **Circuit pattern vector database** — grows with every user design, enables better similarity search and context
2. **Labeled simulation outcomes** — "this circuit passed / this one had a short / this one needed a pull-up" — training data no competitor can buy
3. **Fine-tuned domain model** — trained specifically on electronics design, not general text
4. **Component pricing intelligence** — accumulated knowledge of what's available, at what price, with what lead time
5. **Industry-specific rule libraries** — HVAC rules, refrigeration rules, industrial I/O rules, safety rules — each one built from engineering expertise and user feedback

---

## PART 9 — BUSINESS MODEL

### Pricing Tiers

**Free:** 10 generations per hour, community component library, KiCad export. Purpose: acquire hobbyists and students, build the circuit pattern database.

**Pro — $49/month:** Unlimited generations, unlimited simulation, BOM with live pricing, Gerber export (Phase 2+), version history. Target: freelance engineers, serious makers, IoT startup founders.

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
LTspice is owned by Analog Devices. Its EULA explicitly prohibits commercial redistribution and server-side automation. You cannot legally call LTspice in a SaaS product without a licensing agreement. ngspice is fully open-source (BSD license), SPICE-compatible, scriptable via subprocess. Use ngspice from day one.

**Why the IR must be strict JSON schema (no free text)?**
LLMs hallucinate. They will invent resistor values that don't exist in standard series, specify capacitor voltages below the supply rail, write SPICE syntax that ngspice cannot parse. The IR schema enforces physical constraints at the data layer. If the LLM outputs a capacitor with a 3V rating in a 5V circuit, schema validation rejects it before it reaches the simulation. The retry loop re-prompts with the specific violation.

**Why simulation must be the truth, not the LLM's opinion?**
A language model has no internal physics engine. Simulation runs actual SPICE equations. When simulation says the output voltage is 4.8V not 5V, that is a physics result, not a prediction. The system trusts simulation, not the LLM, for any numerical claim about circuit behavior.

**Why diff-and-patch editing instead of regeneration?**
Regeneration destroys user customizations. The patch model applies changes surgically, preserves everything not explicitly modified, and maintains a complete change history. This is the behavior engineers expect from a professional tool.

**Why start with Arduino/digital and not jump straight to industrial?**
Arduino circuits are deterministic and forgiving. This makes it possible to prove the system works and build user trust before tackling analog circuits. The hobbyist market provides volume — thousands of users generating thousands of designs — which builds the circuit pattern database and training flywheel faster than targeting 50 industrial customers first.

**Why static Python lookup table instead of RAG for Phase 1?**
Datasheet excerpts are 4,000+ tokens each. Embedding 20 components in the system prompt adds 40,000–80,000 tokens per request, exceeds context budget on complex prompts, and costs $0.50–1.00 extra per generation. A Python dict lookup is 0 tokens, 0 latency, 0 cost, and 100% reliable. Qdrant RAG is Phase 2.

---

## PART 11 — WHAT THIS BECOMES

### Short Term (Year 1)
An AI assistant for electronics that hobbyists and indie engineers use to build faster. The market sees it as "ChatGPT for circuits." Revenue comes from Pro subscriptions. Value is speed and error-catching.

### Medium Term (Year 2–3)
A hardware prototyping platform that engineering teams use as their primary design environment. The market sees it as "Cursor for hardware." Revenue comes from Team and early Enterprise contracts. Value is workflow integration and team productivity.

### Long Term (Year 3+)
The standard interface for hardware design. The GCC of physical electronics. Any engineer at any level uses this as their starting point. The market sees it as a new category: Generative Electronic Design Automation (GEDA). Revenue comes from Enterprise contracts and platform fees.

The markets this touches — HVAC controls, building automation, commercial refrigeration, industrial IoT, embedded systems, EV power electronics — collectively represent hundreds of billions of dollars in annual engineering services.

---

## PART 12 — THE SINGLE MOST IMPORTANT THING

If everything in this document is reduced to one thing, it is this:

**The explanation layer is the product.**

Any engineer can run ngspice. Any engineer can open KiCad. What no tool in existence currently does is look at a circuit design and say, in plain English: "I chose this component for this reason. This is what will fail if you change it. This is what you need to check before ordering. Here is what I am not certain about and why."

That reasoning — applied to every component, every connection, every design decision — is what earns the trust of engineers who have been burned by automated tools before. It is what turns a junior engineer into a productive one. It is what a senior engineer shows their client as evidence the design was reviewed. It is what an enterprise buyer points to when justifying the seat license.

Build the explanation layer first. Build it carefully. Build it better than anything else in the product.

Everything else follows from trust.

---

*Document version 2.0 — Part 8 competitive position corrected per Flux.ai 2026 technical documentation, Celus.io product review, and Quilter partner assessment. All other sections unchanged from v1.0.*
