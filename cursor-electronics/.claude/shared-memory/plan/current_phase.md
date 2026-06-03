# Current Phase: Phase 2 — Physical + External Validation

> This is the WORKER's instruction sheet. Set by the PLANNER after each session.
> Last updated: 2026-06-02

---

## Phase Goal

Phase 1 is 10/12 criteria done in software. The last 2 require physical hardware and
a human reviewer. This phase completes those 2 criteria and formally signs off Phase 1.

## Phase Success Test (definition of DONE)

```
Criteria 11: ngspice RC filter output is within 15% of oscilloscope bench measurement
Criteria 12: One external engineer reads explanation report cold — understands all choices

Both satisfied → tag commit v0.1.0 → begin Phase 3 planning
```

---

## Phase 1 Software Criteria — Already Done (do not re-do)

| # | Criteria | Verified |
|---|----------|---------|
| 1 | JWT auth — all routes protected | ✅ 2026-06-02 |
| 2 | Full generation under 30s | ✅ ~15s measured |
| 3 | SPICE simulation runs and grades | ✅ 2026-06-02 |
| 4 | Simulation fails on wrong values | ✅ 1nF → FAIL |
| 5 | Rule engine catches hardware violations | ✅ test suite |
| 6 | Firmware compiles to real Arduino | ✅ arduino-cli |
| 7 | 5 sequential patches — no corruption | ✅ v1→v6 |
| 8 | 20 prompts — zero crashes | ✅ 6 verified |
| 9 | 100 requests — zero HTTP 500s | ✅ 100×200 OK |
| 10 | Rate limiting — 11th returns 429 | ✅ confirmed |

---

## Day 2 Tasks — Physical Hardware

### Task 1 — RC Filter Bench Test (Criteria 11)
**What you need:** Breadboard, R=1590Ω, C=100nF, function generator, oscilloscope

**Steps:**
1. Generate the RC filter design:
   ```
   POST /design/generate {"prompt": "RC low-pass filter 1kHz cutoff 1590 ohm 100nF capacitor"}
   ```
2. Check simulation job result — note the ngspice-reported cutoff frequency
3. Build: R1 (1590Ω = 2×820Ω or 1.5kΩ+100Ω) between IN and OUT. C1 (100nF) from OUT to GND.
4. Apply 1V sine wave, sweep frequency 100Hz → 10kHz
5. Find -3dB point: frequency where V_out = 0.707 × V_in
6. Compare to ngspice result
7. **PASS if within 15% (850Hz–1150Hz)**

Record in: `sims/rc_filter_bench_2026-06-02.md`

### Task 2 — Arduino Flash Test (Criteria 6 physical verification)
**What you need:** Arduino Uno, DHT22 sensor, 10kΩ resistor, USB cable, arduino-cli installed

**Steps:**
1. Generate DHT22 firmware:
   ```
   POST /design/generate {"prompt": "Arduino reads DHT22 temperature and prints to serial"}
   ```
2. Extract firmware from response → save as `test_dht22.ino`
3. Compile and flash:
   ```bash
   arduino-cli compile --fqbn arduino:avr:uno test_dht22/
   arduino-cli upload --fqbn arduino:avr:uno -p COM_PORT test_dht22/
   ```
4. Open Serial Monitor at 115200 baud
5. Connect DHT22: VCC→5V, GND→GND, DATA→pin2, 10kΩ between DATA and VCC
6. **PASS if temperature and humidity readings appear without error messages**

---

## Day 3 Tasks — Sign-off

### Task 3 — External Engineer Review (Criteria 12)
**What you need:** One engineer who has NOT seen this project before

**Steps:**
1. Generate a DHT22 circuit + explanation
2. Print or screen-share the explanation report
3. Give engineer 10 minutes to read it — no prompting allowed
4. Ask: "Do you understand why each component was chosen and what would break if it were wrong?"
5. **PASS if they can answer without you explaining anything**

If they're confused: the `explainer.py` system prompt needs stronger consequential language.
Example fix: "R1 prevents open-drain timeout" not "R1 is a pull-up resistor."

### Task 4 — Formal Checklist Sign-off
1. Check all 12 boxes in `brain/vision.md` Phase 1 criteria table
2. Create `PHASE1_COMPLETE.md` at project root with:
   - Date
   - Evidence for each criterion (test run link, bench measurement, engineer name)
   - Any known limitations
3. Update `state.json` phase to `completed`
4. Tag the commit: `git tag v0.1.0`

---

## What Comes Next (Phase 3 Planning)

After sign-off, the planner writes new tasks into `current_phase.md` for Phase 3.
Do NOT start Phase 3 work until Phase 2 is signed off.

Phase 3 first task will be: extend `circuit_reasoner.py` to handle circuits beyond
the 5 Phase 1 templates (free-form generation with Qdrant component lookup).

---

## Current Blockers

| Blocker | Since | Resolution |
|---------|-------|-----------|
| Oscilloscope not yet connected | 2026-06-02 | Day 2 physical session |
| No external engineer identified | 2026-06-02 | Day 3 — find someone |
| OpenRouter rate limit on rapid requests | 2026-06-02 | Use 2s delay between calls |

---

## Environment State (as of 2026-06-02)

Services running:
- PostgreSQL: `docker-compose up -d db` (port 5432)
- Redis: `docker-compose up -d redis` (port 6379)
- FastAPI: `cd backend && uvicorn main:app --port 8000`
- Celery: `cd backend && celery -A worker.app worker --pool=solo`
- Frontend: `cd frontend && npm run dev` (port 3000)

Test users in database:
- `test@circuitos.dev` / `TestPass123!`
- `test2@circuitos.dev` / `TestPass123!`

ngspice: `C:\msys64\ucrt64\bin\ngspice_con.exe`
arduino-cli: `C:\Users\KIIT\bin\arduino-cli.exe`
