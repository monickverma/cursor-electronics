# Step 3 — Sign the 12 proven properties

Each sentence below was generated from the formula z3 proved. It wasn't written by hand, so the sentence is the claim. Sign only what you understand and believe. If you're unsure about one, leave it unsigned: one honest gap is worth more than twelve rubber stamps.

**How a signature lands.** A signature covers a design's whole property set, by `properties_hash`. Generate the design (form or prompt, with the fields below), then sign it in the UI, or with `POST /design/{id}/sign-off` and the hash shown. Any patch drops the signature by design.

**What it changes.** The proofs are all G1 already. The voltage divider's floor stays at **G2** until it's signed, because unsigned designs still show the old Stage 3 interval bound. Signing moves the library's weakest grade to G1. It doesn't touch D1 (bench) or D7 (figures).

**Before you sign, be able to answer these for each property:** Where do the ranges come from (the part tolerance)? What is held fixed? What would a counterexample look like? If you can't, read `backend/proof/prover.py::compile_statement` for that kind of property first.

## voltage_divider — fields `{"vout_v": 3.3, "supply_v": 5}` · floor now G2

`properties_hash` 1775dcbac8d2508ba73c424a5db9b3f897feb117f5190bd738d9faa7e00d8b49

1. ☐ **divider.vout** (proven, G1) — For every R1 from 3.366 kΩ to 3.434 kΩ (1% resistor); every R2 from 6.5835 kΩ to 6.7165 kΩ (1% resistor), with VIN held at 5 V, the voltage at VOUT stays between 3.28 V and 3.34 V.

2. ☐ **divider.r1_power** (proven, G1) — For every R1 from 3.366 kΩ to 3.434 kΩ (1% resistor); every R2 from 6.5835 kΩ to 6.7165 kΩ (1% resistor), with VIN held at 5 V, R1's dissipation never exceeds 62.5 mW.

3. ☐ **divider.r2_power** (proven, G1) — For every R1 from 3.366 kΩ to 3.434 kΩ (1% resistor); every R2 from 6.5835 kΩ to 6.7165 kΩ (1% resistor), with VIN held at 5 V, R2's dissipation never exceeds 62.5 mW.

Signed by ______ on ______ · or left unsigned because: ______

## led_indicator — fields `{"led_current_ma": 10, "mcu": "arduino_uno"}` · floor now G1

`properties_hash` a3e1229b0233113da5f5f24e35f318740ea184a327dabd9233f9deb3b33d7c12

4. ☐ **led.current** (proven, G1) — For every U1 pin resistance from 15 Ω to 40 Ω (datasheet V_OH figure); every R1 from 277.2 Ω to 282.8 Ω (1% resistor), with VCC_5V held at 5 V, the MCU pin driving LED_CTRL high at 5 V, LED1's forward voltage anywhere from 1.6 V (assumed: the datasheet gives no minimum) to its datasheet maximum of 2.4 V at 20 mA, the LED current stays between 8.19 mA and 11.8 mA.

5. ☐ **led.gpio_current** (proven, G1) — For every U1 pin resistance from 15 Ω to 40 Ω (datasheet V_OH figure); every R1 from 277.2 Ω to 282.8 Ω (1% resistor), with VCC_5V held at 5 V, the MCU pin driving LED_CTRL high at 5 V, LED1's forward voltage anywhere from 1.6 V (assumed: the datasheet gives no minimum) to its datasheet maximum of 2.4 V at 20 mA, the current U1's pin sources never exceeds 20 mA.

6. ☐ **led.led_current** (proven, G1) — For every U1 pin resistance from 15 Ω to 40 Ω (datasheet V_OH figure); every R1 from 277.2 Ω to 282.8 Ω (1% resistor), with VCC_5V held at 5 V, the MCU pin driving LED_CTRL high at 5 V, LED1's forward voltage anywhere from 1.6 V (assumed: the datasheet gives no minimum) to its datasheet maximum of 2.4 V at 20 mA, the LED current never exceeds 30 mA.

7. ☐ **led.r1_power** (proven, G1) — For every U1 pin resistance from 15 Ω to 40 Ω (datasheet V_OH figure); every R1 from 277.2 Ω to 282.8 Ω (1% resistor), with VCC_5V held at 5 V, the MCU pin driving LED_CTRL high at 5 V, LED1's forward voltage anywhere from 1.6 V (assumed: the datasheet gives no minimum) to its datasheet maximum of 2.4 V at 20 mA, R1's dissipation never exceeds 62.5 mW.

Signed by ______ on ______ · or left unsigned because: ______

## rc_lowpass — fields `{"cutoff_hz": 1000, "supply_v": 5}` · floor now G1

`properties_hash` 979c063b769a05afa44bad81a61d63e490c6fe30ab12f8279659a445c2bff566

8. ☐ **rc.cutoff** (proven, G1) — For every R1 from 3.366 kΩ to 3.434 kΩ (1% resistor); every C1 from 42.3 nF to 51.7 nF (10% capacitor), with IN driven by the AC source, the −3 dB cutoff frequency at OUT stays between 896 Hz and 1.12 kHz.

Signed by ______ on ______ · or left unsigned because: ______

## dht22_node — fields `{"mcu": "arduino_uno"}` · floor now G1

`properties_hash` 1cc0283d37106b7fe7a9f9c7ac23dccf41a4e2429c45218dd8749a4a14525551

9. ☐ **dht.rise_time** (proven, G1) — For every R1 from 9.9 kΩ to 10.1 kΩ (1% resistor); every DATA line capacitance from 35 pF to 50 pF (both pins, plus 0.3 m of cable at 50–100 pF/m), with VCC_5V held at 5 V, DATA's 10–90 % rise time never exceeds 5 µs.

10. ☐ **dht.sink_current** (proven, G1) — For every R1 from 9.9 kΩ to 10.1 kΩ (1% resistor), with VCC_5V held at 5 V, DATA held at 0 V (the MCU's start pulse, or the sensor's reply), the current into whatever holds DATA low never exceeds 4 mA.

Signed by ______ on ______ · or left unsigned because: ______

## rs485_node — fields `{"mcu": "arduino_uno"}` · floor now G1

`properties_hash` 71f0e291c6be3d6c8ab97423bc8b2c48413a340895f1e8e43d5bc32efc968dbc

11. ☐ **rs485.failsafe_bias** (proven, G1) — For every R1 from 118.8 Ω to 121.2 Ω (1% resistor); every R2 from 543.51 Ω to 554.49 Ω (1% resistor); every R3 from 543.51 Ω to 554.49 Ω (1% resistor); every far-end terminator from 118.8 Ω to 121.2 Ω (1%, at the other end of the bus), with VCC_5V held at 5 V, the idle bus voltage V(A) − V(B) never falls below 200 mV.

12. ☐ **rs485.driver_load** (proven, G1) — For every R1 from 118.8 Ω to 121.2 Ω (1% resistor); every R2 from 543.51 Ω to 554.49 Ω (1% resistor); every R3 from 543.51 Ω to 554.49 Ω (1% resistor); every far-end terminator from 118.8 Ω to 121.2 Ω (1%, at the other end of the bus), with VCC_5V held at 5 V, the resistance the driver sees across A–B never falls below 54 Ω.

Signed by ______ on ______ · or left unsigned because: ______

