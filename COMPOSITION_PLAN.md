# Composition — from five circuits to real projects

> Proposal, 2026-10-03. Status: **approved 2026-10-03; M1–M4 built 2026-10-03** (`brain/decisions.md` [2026-10-03]). The live LLM run of
> the target sentence waits on API credits; the bench build waits on the parts.
> Target sentence: *"Room monitor: an Uno reads a DHT22, sounds a buzzer above 30 °C, and lights a status LED."*
> Done means: that sentence produces one board with a schematic, firmware that compiles, a BOM and graded
> claims, and you can build it from the outputs.

## Why this, and why now

Today every design is exactly one generator's output. Each generator builds its own MCU, rail and pins, so two
blocks can't share a board, and "DHT22 + LED" is impossible. Phase 2 made those single blocks trustworthy.
Composition is what makes them useful. It was planned from the start: every generator's `envelope()` already
returns `PortContract`s for this (`ARCHITECTURE_ASSURANCE_CASE.md` §4, "grade: none until two generators share a
rail").

## The One Rule still holds

The LLM writes **JSON only**: a list of blocks and a list of behaviour rules from a closed vocabulary. It never
writes pins, the circuit or firmware.

```json
{"function": "project", "constraints": {"mcu": "arduino_uno", "supply_v": 5},
 "blocks": [
   {"id": "climate", "function": "temperature_humidity_sensor", "constraints": {"cable_length_m": 0.3}},
   {"id": "alarm",   "function": "buzzer"},
   {"id": "status",  "function": "led_indicator", "targets": {"led_current_ma": 10}}],
 "behaviour": [
   {"when": {"block": "climate", "reads": "temperature_c", "op": ">", "value": 30},
    "then": {"block": "alarm", "set": "on"}},
   {"always": {"block": "status", "set": "heartbeat"}}]}
```

The firmware is compiled from the behaviour rules by a Jinja template, as it is today.

## Milestones

| # | What | Result you can see | Estimate |
|---|---|---|---|
| M1 | **Composer:** `generators/compose.py` dispatches each block through the registry on one board. It allocates pins with the existing `pin_rules` (the board defaults collide: Uno D2 is both DHT22 data and RS-485 DE; on the ESP32 the LED and DHT22 are both GPIO4). It merges everything into one CircuitIR with one MCU, one rail and one ground, and renumbers parts. | DHT22 + LED on one Uno: schematic, SPICE and BOM | 1 week |
| M2 | **Behaviour:** the closed `when/then/always` vocabulary in IntentIR and a composite firmware template. The compile gate is unchanged. | Firmware that reads the DHT22 and drives the LED from a rule, compiling under PlatformIO | 1 week |
| M3 | **Load-switch block:** a new generator, an NPN low-side switch with a base resistor and a flyback diode where the load is inductive. It's proved like the others: base current within the pin's limit, transistor saturated, load current within its rating. The buzzer is its first load, and the **same block later drives relays, motors and pumps.** | The buzzer in the room monitor | 1–1.5 weeks |
| M4 | **Board-level checks and the front door:** total rail current against the board's supply (from `PortContract.current_draw_a`), the cross-block pin check, and an honest composed grade (each block's proofs hold under the stated side condition that the shared rail stays in range). The LLM producer and form learn `project`. The UI shows the blocks. | **Type the room-monitor sentence and get the board.** | 1 week |

That's about 4–5 weeks to the first real multi-part design. Each milestone ends with something running, not just
tests.

## After M4: blocks chosen by demand

The next likely blocks: relay (the M3 load switch), OLED (I2C, whose pull-up rule already exists), analog soil
or light sensor, servo, push button. The order comes from what people actually ask for, which is where
`fieldwork/5_user_trial.md` comes in.

## What this does not do

- No PCB or Gerber output. The output stays a breadboard-able schematic plus firmware, as today.
- No free-form circuits. Every block is still a proved generator; a request that needs a block nobody has
  written is refused by name, and that refusal is the backlog.
- No new defeaters or other assurance machinery beyond what composition itself needs.

## Decided 2026-10-03: the buzzer drive

**The buzzer drive.** The recommendation is to switch it with a transistor (the M3 load-switch block), because
that same block then runs relays, motors and pumps. The cheaper alternative is a passive piezo driven straight
from a pin with `tone()`. It's faster to build, but it's a dead end: nothing else reuses it.
