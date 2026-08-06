# Decisions — LAYER 3

> Append-only. Never delete. Each entry answers: "why THIS way?"
> Format: decision → reason → alternatives rejected → date

---

## [2026-06-01] LLM writes JSON, not SPICE/KiCad/firmware directly

**Decision:** The LLM only ever produces CircuitIR JSON. Deterministic compilers
(Python functions) translate that JSON to SPICE, .kicad_sch, .ino, BOM.

**Reason:**
- LLM-generated SPICE hallucinates component models, wrong node names, broken syntax
- LLM-generated firmware uses wrong pin numbers, missing includes, imaginary libraries
- JSON → compiler is testable, reproducible, and debuggable
- One schema change (CircuitIR) updates all downstream formats simultaneously

**Alternatives rejected:**
- LLM writes SPICE directly — fails silently, no schema validation
- Template-free firmware — hallucinates DHT library function names

---

## [2026-06-01] tool_use mode only — never raw LLM text

**Decision:** All AI calls use `tool_choice={"type":"tool","name":"..."}` forcing
structured output. `response.content[0].input` is already a parsed dict.

**Reason:**
- Raw text responses require JSON extraction regex, markdown fence stripping
- tool_use eliminates the entire class of JSON parse errors
- Forces the model to produce a schema-conforming structure or fail cleanly

---

## [2026-06-01] ngspice not LTspice

**Decision:** ngspice is the SPICE engine.

**Reason:**
- LTspice EULA explicitly prohibits server-side automation and commercial use
- ngspice is BSD licensed — free for commercial SaaS
- ngspice is already integrated into KiCad

**Non-negotiable.** Do not add LTspice support.

---

## [2026-06-01] Jinja2 templates for firmware, not LLM generation

**Decision:** .ino files are rendered from Jinja2 templates (sensor_read.ino.j2,
modbus_master.ino.j2, base.ino.j2).

**Reason:**
- LLM-generated firmware hallucinates function names (DHT.readTemp vs dht.readTemperature)
- Templates produce identical output for identical input — testable
- arduino-cli compilation test can verify every template on every CI run

---

## [2026-06-01] Celery not inline simulation

**Decision:** All ngspice runs go through Celery tasks.

**Reason:**
- `await` releases the event loop but NOT the HTTP connection
- 30-second simulation would cause browser/load-balancer timeout
- Celery gives job_id → client polls → scales horizontally

---

## [2026-06-01] Static component_constraints.py not Qdrant RAG

**Decision:** Component constraints are a Python dict, not a vector database.

**Reason:**
- Datasheet excerpts are 4,000+ tokens each — $0.50–1.00 per generation call if embedded
- Python dict lookup is 0 tokens, 0 latency, 100% reliable
- Phase 2 adds Qdrant when breadth requires it

---

## [2026-06-01] Net labels in KiCad, not wire routing

**Decision:** KiCad schematic uses net labels to connect components, not wire routes.

**Reason:**
- Wire routing requires exact pin coordinates from KiCad symbol library for each component
- Net labels connect by name — generatable without a symbol library lookup
- Phase 3 adds proper wire routing

---

## [2026-06-01] bcrypt directly, not passlib

**Decision:** Password hashing uses `import bcrypt` directly.

**Reason:**
- passlib 1.7.4 is incompatible with bcrypt 4.x
- Direct bcrypt is simpler and avoids the dependency conflict

---

## [2026-06-01] No in-memory design storage

**Decision:** Every CircuitIR is persisted to PostgreSQL immediately after generation.

**Reason:**
- In-memory dict dies on server restart
- Breaks with multiple Celery workers
- Patch history and audit trail require persistent storage

---

## [2026-06-02] OpenRouter base_url must omit /v1

**Decision:** `ANTHROPIC_BASE_URL=https://openrouter.ai/api` (no /v1 suffix).

**Reason:**
- The Anthropic SDK appends `/v1/messages` to whatever base_url is set
- Setting base_url to `.../api/v1` results in `.../api/v1/v1/messages` → 404
- Verified by intercepting the HTTP request with custom httpx.HTTPTransport

**Applied in:** `backend/core/config.py`, `.env`, `.env.example`

---

## [2026-06-02] ngspice on Windows requires -o flag, not stdout pipe

**Decision:** `NgspiceRunner._run_sync()` uses `ngspice_con -b -o outfile.out infile.cir`
and reads the output file rather than capturing stdout.

**Reason:**
- ngspice_con.exe is a Windows console application that writes directly to the
  Windows console handle (CONOUT$), bypassing stdout/stderr pipes entirely
- `subprocess.run(capture_output=True)` always returns empty strings
- Verified: piping to file via `-o` captures all output correctly

**Applied in:** `backend/simulation/runner.py`

---

## [2026-06-02] ngspice AC output: magnitude = sqrt(real^2 + imag^2)

**Decision:** AC simulation values are computed as complex magnitude, not real part.

**Reason:**
- ngspice AC output format: `idx  freq  real,  imag` (complex pair, comma-separated)
- At 1kHz RC filter: real=2.502V, imag=-2.500V
- Real part alone = 2.502V (29% error vs expected 3.536V)
- sqrt(2.502^2 + 2.500^2) = 3.536V (exactly -3dB ✓)

**Applied in:** `backend/simulation/parser.py` → `_parse_ac_table()`

---

## [2026-06-02] ngspice emits separate table per variable even on single .print line

**Decision:** AC parser handles MULTIPLE tables (one per node) and merges by freq_idx.

**Reason:**
- `.print ac v(in) v(out)` — looks like one command
- ngspice still emits two separate tables, one for v(in), one for v(out)
- Plus paginates each table at ~55 rows repeating the header
- Parser must: find ALL headers, parse each table, merge by index into final result

**Applied in:** `backend/simulation/parser.py` → `_parse_ac_table()` full rewrite

---

## [2026-06-02] Celery on Windows Python 3.13 needs --pool=solo

**Decision:** Start Celery worker with `--pool=solo`.

**Reason:**
- Celery 5.x + billiard prefork + Python 3.13 on Windows fails with:
  `ValueError: not enough values to unpack (expected 3, got 0)` in fast_trace_task
- `--pool=solo` runs tasks in the main process, bypassing billiard
- Acceptable for single-machine dev; production Docker image (Linux) uses default pool

---

## [2026-06-02] Arduino Uno Modbus uses SoftwareSerial, not Serial1

**Decision:** `modbus_master.ino.j2` uses `SoftwareSerial` on pins 10/11 for RS-485.

**Reason:**
- Arduino Uno has only one hardware UART (`Serial` on pins 0/1)
- `Serial1` exists on Mega/Leonardo only
- `SoftwareSerial` is bit-banged on any two pins — works on Uno
- `Serial` (pins 0/1) stays free for debug output to Serial Monitor

---

## [2026-06-02] .env path resolved from config.py location, not CWD

**Decision:** `config.py` uses `Path(__file__).parent.parent.parent / ".env"`.

**Reason:**
- `env_file=".env"` resolves relative to CWD at runtime
- Running `uvicorn` from `backend/` directory looks for `backend/.env` (doesn't exist)
- The actual `.env` is at project root
- `Path(__file__)` always knows where config.py is, regardless of launch directory

---

## [2026-06-02] Rate limiting is IP-based (slowapi default)

**Decision:** Rate limits apply per IP address, not per user/token.

**Reason:**
- slowapi's default key function uses the request IP
- All localhost development traffic shares the 10/hour generate limit
- For production: override key function to use user ID from JWT

**Known limitation:** In dev, hitting the limit blocks all users from the same machine.
Use a second test account and wait 1 hour, or temporarily raise the limit in .env.

---

## [2026-08-07] Criterion 11 gate changed from bench measurement to analytical cross-check

**Decision:** The Phase 1 simulation-accuracy gate is an analytical cross-check
against closed-form circuit equations at 2% tolerance, not an oscilloscope
measurement at 15% tolerance.

**Reason:**
- No oscilloscope or function generator is available, and none is expected.
  The criterion had been blocking Phase 1 sign-off since 2026-06-02 with no path forward.
- The failure mode criterion 11 actually guards against is a netlist generator
  that emits plausible but incorrect SPICE. That risk lives in
  `backend/generators/netlist/spice.py` — code written here. ngspice itself is a
  mature, independently validated simulator; it is not the thing under test.
- Comparing ngspice output to `f = 1/(2πRC)` catches netlist-generation bugs
  directly, with no hardware dependency.

**Tolerance changed 15% → 2%:** the 15% figure existed to absorb physical
component tolerance (±5% resistors, ±10% capacitors) plus probe and breadboard
error. In a purely analytical comparison none of that exists, so a 15% gate
would pass a generator with a real scaling bug. Anything beyond ~2% is a defect.

**Recorded limitation:** this validates the netlist generator against
mathematics, not against physical reality. It cannot catch parasitic
capacitance, contact resistance, or a real component operating outside its
datasheet. Criterion 11 is therefore marked `met_by_substitute`, never `met`.
When lab access becomes available, run the original bench test and upgrade it.
The product's public claim is "simulates before it ships" — that claim is owed a
physical measurement eventually.

---

## [2026-08-07] Memory trackers require explicit module registration

**Decision:** Every new backend module must be registered in BOTH
`tools/regen_state.py` (`MODULES`) and `tools/progress_gen.py` (`PLANNED`) in the
same commit that introduces it.

**Reason:**
- Both tools iterate a hardcoded dict. An unregistered module is not reported as
  untested — it is not reported at all.
- `backend/pcb_engine/` (~2,400 lines across 7 modules) went untracked for
  roughly two months. During that time `progress.yaml` reported 84.4% verified.
  With the PCB engine registered, the honest figure is 48.3%.
- The reported number was never false. Its denominator was silently wrong, which
  is worse than a visibly failing test — it looks like health.

**Consequence:** entry count went 32 → 60 and verified percentage 84.4% → 48.3%
on 2026-08-07. The drop reflects better accounting, not a regression. Do not
"restore" the old number.

**Better fix, deferred:** make the trackers walk `backend/` and auto-discover
modules so this class of bug cannot recur. Not done yet — it is a larger change
to the tooling and was out of scope for the re-sync session.
