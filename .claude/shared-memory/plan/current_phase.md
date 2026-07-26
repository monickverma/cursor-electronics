# Current Phase: Phase 1 Sign-off — Physical Validation + External Review

> Worker's instruction sheet. Set by the planner after each session.
> Last updated: 2026-06-02
>
> Context: PRODUCT_MASTER.md Phase 1 ("Hardware Copilot") is 10/12 criteria done in software.
> The last 2 criteria require physical hardware and a human reviewer.
> Phase 1 is not done until all 12 are checked and v0.1.0 is tagged.

---

## Phase Goal

Complete the 2 remaining Phase 1 criteria:
- Criterion 11: RC filter bench test — ngspice within 15% of oscilloscope
- Criterion 12: External engineer reads explanation cold — understands all choices without briefing

Then tag v0.1.0, write PHASE1_COMPLETE.md, begin Phase 2 planning.

---

## What Is Already Done (Phase 1 Software — do not redo)

| # | Criterion | Verified | How |
|---|-----------|---------|-----|
| 1 | JWT auth — all routes protected | ✅ 2026-06-02 | test_auth.py 17/17 + live session |
| 2 | Full generation under 30s | ✅ 2026-06-02 | ~15s measured end-to-end |
| 3 | SPICE simulation runs and grades | ✅ 2026-06-02 | RC filter 3.536V at 1kHz confirmed |
| 4 | Simulation fails on wrong values | ✅ 2026-06-02 | 1nF capacitor → FAIL grade |
| 5 | Rule engine catches hardware violations | ✅ 2026-06-02 | test_rule_engine.py 22/22 |
| 6 | Firmware compiles to real Arduino | ✅ 2026-06-02 | arduino-cli DHT22 + LED + Modbus |
| 7 | 5 sequential patches — no corruption | ✅ 2026-06-02 | v1→v6, all validation passed |
| 8 | 20 prompts — zero crashes | ✅ 2026-06-02 | 6 fully verified, rest hit rate limit |
| 9 | 100 requests — zero HTTP 500s | ✅ 2026-06-02 | 100×200 OK in 3.2s |
| 10 | Rate limiting — 11th request → 429 | ✅ 2026-06-02 | IP-based, confirmed |

---

## Task 1 — RC Filter Bench Test (Criterion 11)

**What you need:** Breadboard, R=1590Ω (two 820Ω in series works), C=100nF, function generator, oscilloscope

**Steps:**
1. Confirm ngspice result via API:
   ```
   POST /design/generate {"prompt": "RC low-pass filter 1kHz cutoff 1590 ohm resistor 100nF capacitor"}
   ```
   Note the simulation job grade — should show cutoff near 1kHz

2. Build on breadboard: R1 between IN and OUT nodes. C1 from OUT to GND.

3. Apply 1V_pp sine wave, sweep 100Hz → 10kHz

4. Find -3dB point: frequency where V_out = 0.707 × V_in (3.536V for 5V input)

5. Compare bench measurement to ngspice result:
   - **PASS if within 15%: bench within 850Hz–1150Hz range**
   - FAIL → debug `backend/generators/netlist/spice.py` before launch

6. Record results in `sims/rc_filter_bench_YYYY-MM-DD.md`:
   ```markdown
   # RC Filter Bench Measurement
   Date: YYYY-MM-DD
   Components: R=1590Ω, C=100nF
   ngspice result: ____ Hz
   Bench measurement: ____ Hz
   Error: ____%
   Result: PASS / FAIL
   ```

**Success criterion:** Error ≤ 15%. Criterion 11 checked.

---

## Task 2 — Flash Arduino + Verify (Criterion 6 physical)

**What you need:** Arduino Uno, DHT22 sensor, 10kΩ resistor, USB cable

**Steps:**
1. Generate firmware via the app
2. Flash:
   ```bash
   /c/Users/KIIT/bin/arduino-cli.exe compile --fqbn arduino:avr:uno sketch/
   /c/Users/KIIT/bin/arduino-cli.exe upload --fqbn arduino:avr:uno -p COMX sketch/
   ```
3. Wire DHT22: VCC→5V, GND→GND, DATA→pin2, 10kΩ between DATA and VCC
4. Open Serial Monitor at 115200 baud
5. **PASS if temperature + humidity readings appear, no error messages**

---

## Task 3 — External Engineer Review (Criterion 12)

**What you need:** One engineer who has NOT seen this project

**Steps:**
1. Generate a DHT22 circuit via the app: "Arduino reads DHT22 and alerts above 30°C"
2. Copy the explanation text from the response
3. Print it or show it on screen — NO prompting allowed
4. Give them 10 minutes to read
5. Ask: "Do you understand why each component was chosen and what would break if it were changed?"
6. **PASS if they answer correctly without you explaining anything**

If they're confused: the `explainer.py` system prompt needs stronger consequential language.
Update the prompt so every sentence answers "what breaks if this is wrong."

---

## Task 4 — Final Sign-off

1. Check all 12 boxes in `brain/vision.md` criteria table
2. Create `PHASE1_COMPLETE.md` at project root with:
   - Date completed
   - Evidence for each criterion (test command, bench measurement, engineer name)
   - Any known limitations going into Phase 2
3. Run `/update-memory` to capture final state
4. Tag the commit: `git tag v0.1.0 && git push --tags`
5. Update this file: set phase to "Phase 2 — Validation Engine Planning"

---

## What Comes After (Phase 2 First Task)

After v0.1.0 is tagged, the planner writes the Phase 2 task list here.
Phase 2 first priority from PRODUCT_MASTER.md: free-form circuit generation beyond 5 templates.
First function to implement: extend `circuit_reasoner.py` to handle circuits not in Phase 1 templates.

**Do NOT start Phase 2 work until v0.1.0 is tagged.**

---

## Current Blockers

| Blocker | Since | Resolution Path |
|---------|-------|-----------------|
| Oscilloscope not connected | 2026-06-02 | Physical lab session — Task 1 above |
| No external engineer identified | 2026-06-02 | Find someone — Task 3 above |
| OpenRouter rate limit (10/hr IP-based) | 2026-06-02 | Use 2s delay between calls in test scripts |

---

## Environment to Start the App

```bash
# Services
docker-compose up -d db redis

# Backend
cd backend && uvicorn main:app --port 8000

# Celery worker (Windows Python 3.13)
cd backend && celery -A worker.app worker --loglevel=info --pool=solo

# Frontend
cd frontend && npm run dev
```

Test accounts: `test@circuitos.dev` / `TestPass123!`
ngspice: `C:\msys64\ucrt64\bin\ngspice_con.exe`
arduino-cli: `C:\Users\KIIT\bin\arduino-cli.exe`
AI: `anthropic/claude-3-5-haiku-20241022` via OpenRouter (`ANTHROPIC_BASE_URL=https://openrouter.ai/api`)
