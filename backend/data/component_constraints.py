"""
Component constraint lookup table. Zero LLM tokens.
The circuit reasoner injects only the relevant entries for components it is considering.
"""

COMPONENT_CONSTRAINTS: dict[str, dict] = {
    "DHT22": {
        "supply_voltage_min": 3.3,
        "supply_voltage_max": 5.5,
        "current_draw_ma": 2.5,
        "required_pullup_on_pins": ["DATA"],
        "pullup_value_kohm": 10,
        "pullup_to": "VCC",
        "protocol": "single_wire_dht",
        "min_sample_interval_ms": 2000,
        # Bus-timing inputs for the DHT22 generator's rise-time and sink-current
        # claims (Stage 3). Aosong's datasheet gives the protocol timing (a "0"
        # bit is 26-28 us high) but not these; they are stated assumptions,
        # recorded here once and cited through defeater D7.
        #  - cable capacitance: 50-100 pF/m covers ribbon to twisted pair
        #  - input capacitance: ~10 pF each for the MCU pin and the sensor
        #  - rise time: <= 5 us, a 5x margin inside the 26 us short-bit window
        #  - sink current: <= 4 mA through the sensor's open-drain output, the
        #    conservative figure open-drain buses (I2C: 3 mA) are designed to
        "bus_capacitance_pf_per_m": {"min": 50.0, "max": 100.0},
        "input_capacitance_pf": 10.0,
        "rise_time_limit_us": 5.0,
        "open_drain_sink_limit_ma": 4.0,
        "notes": [
            "DATA pin requires 10kΩ pull-up to VCC (3.3V or 5V)",
            "Cannot be read faster than once every 2 seconds",
            "Provides temperature ±0.5°C and humidity ±2%RH",
            "Open-drain output — will not communicate without pull-up",
        ],
    },
    "DHT11": {
        "supply_voltage_min": 3.3,
        "supply_voltage_max": 5.5,
        "current_draw_ma": 2.5,
        "required_pullup_on_pins": ["DATA"],
        "pullup_value_kohm": 10,
        "pullup_to": "VCC",
        "protocol": "single_wire_dht",
        "min_sample_interval_ms": 1000,
        "notes": [
            "DATA pin requires 10kΩ pull-up to VCC",
            "Lower accuracy than DHT22: temperature ±2°C, humidity ±5%RH",
        ],
    },
    "MAX485ECSA": {
        "supply_voltage_min": 4.75,
        "supply_voltage_max": 5.25,
        "current_draw_ma": 0.3,
        "de_re_pins_tied": True,
        "de_re_drive": "MCU_GPIO",
        "requires_termination_ohm": 120,
        "termination_placement": "between_A_and_B_at_bus_endpoints",
        "requires_bias": True,
        "bias_value_ohm": 560,
        "bias_a_to": "VCC",
        "bias_b_to": "GND",
        "decoupling_cap_nf": 100,
        # Bus figures for the RS-485 generator's fail-safe and load claims
        # (Stage 3). TIA-485-A: a receiver must resolve |V_AB| >= 200 mV, and a
        # driver is specified into a 54 ohm differential load (two 120 ohm
        # terminators and 32 unit loads). The driver cannot swing more than
        # its supply, so V_CC bounds the terminator's worst-case dissipation.
        # Datasheet/standard-derived: defeater D7.
        "receiver_threshold_mv": 200.0,
        "driver_rated_load_ohm": 54.0,
        "notes": [
            "DE and RE pins must be tied together and driven by one MCU GPIO",
            "HIGH = transmit mode, LOW = receive mode",
            "120Ω termination resistor required between A and B at both ends of long bus",
            "560Ω bias resistors: A-line to VCC, B-line to GND",
            "100nF decoupling capacitor on VCC pin — place close to IC",
            "Logic levels: 5V only (MAX485) or 3.3V (MAX3485)",
        ],
    },
    "MAX3485ECSA": {
        "supply_voltage_min": 3.0,
        "supply_voltage_max": 3.6,
        "current_draw_ma": 0.3,
        "de_re_pins_tied": True,
        "requires_termination_ohm": 120,
        "requires_bias": True,
        "bias_value_ohm": 560,
        "decoupling_cap_nf": 100,
        # Stage 5: the same TIA-485 bus figures as the MAX485 — the standard
        # sets them, not the part. Defeater D7.
        "receiver_threshold_mv": 200.0,
        "driver_rated_load_ohm": 54.0,
        "notes": [
            "3.3V version of MAX485. Use when MCU logic is 3.3V.",
            "Same wiring as MAX485 but 3.3V supply and logic levels.",
        ],
    },
    "ATmega328P-PU": {
        "supply_voltage_min": 1.8,
        "supply_voltage_max": 5.5,
        "max_gpio_source_current_ma": 40,
        "max_gpio_sink_current_ma": 40,
        "max_total_io_current_ma": 200,
        "pwm_pins_arduino_uno": ["3", "5", "6", "9", "10", "11"],
        "i2c_pins": {"SDA": "A4", "SCL": "A5"},
        "uart0_pins": {"TX": "D1", "RX": "D0"},
        "spi_pins": {"MOSI": "D11", "MISO": "D12", "SCK": "D13", "SS": "D10"},
        "adc_pins": ["A0", "A1", "A2", "A3", "A4", "A5"],
        "flash_kb": 32,
        "ram_bytes": 2048,
        # Output drive, for the Thevenin pin model (Stage 3, `mcu_pin_thevenin`).
        # Datasheet §28.2: V_OH >= 4.2 V at I_OH = 20 mA, VCC = 5 V -> at most
        # (5 - 4.2) / 0.02 = 40 ohm. Typical curves sit near 25 ohm. Read by
        # both spice.py and the LED generator, so the netlist and predict()
        # cannot disagree about the pin. Datasheet-derived: defeater D7.
        "gpio_output_resistance_ohm": {"min": 15.0, "typ": 25.0, "max": 40.0},
        "gpio_recommended_current_ma": 20,
        # Supply-load model (X6, `mcu_as_100R`, D2): 100 ohm on the 5 V rail.
        "supply_model_ohm": 100.0,
        "notes": [
            "Max 40mA per GPIO pin — LED without current limiter will damage the MCU",
            "Max 200mA total from all I/O pins combined",
            "PWM only on pins 3, 5, 6, 9, 10, 11 (marked ~ on Arduino board)",
            "I2C requires external 4.7kΩ pull-up on both SDA (A4) and SCL (A5)",
            "5V logic — do NOT connect 3.3V-only devices without level shifting",
        ],
    },
    "ESP32-WROOM-32D": {
        "supply_voltage_min": 3.0,
        "supply_voltage_max": 3.6,
        "max_gpio_current_ma": 40,
        "current_draw_active_ma": 80,
        "current_draw_deep_sleep_ua": 10,
        "wifi": True,
        "bluetooth": True,
        "i2c_pins_configurable": True,
        "uart_count": 3,
        "spi_count": 4,
        "notes": [
            "3.3V logic — do NOT connect 5V signals without level shifting",
            "GPIO34–39 are input-only (no output, no pull-up/pull-down)",
            "GPIO6–11 are connected to internal flash — DO NOT USE",
            "WiFi transmit draws up to 500mA peak — supply must handle this",
            "100nF + 10μF decoupling on 3.3V supply",
        ],
    },
    # Stage 5 targets. The ESP32-DevKitC carries the WROOM-32E; the entry above
    # is the older 32D and is left as it was.
    "ESP32-WROOM-32E": {
        "supply_voltage_min": 3.0,
        "supply_voltage_max": 3.6,
        "max_gpio_current_ma": 40,
        # Datasheet DC characteristics: V_OH >= 0.8 x VDD (2.64 V) at the pin's
        # rated source current. At the default drive strength (level 2, the
        # Arduino core's) that is 20 mA -> at most (3.3 - 2.64) / 0.02 = 33 ohm.
        # Defeater D7.
        "gpio_output_resistance_ohm": {"min": 10.0, "typ": 20.0, "max": 33.0},
        "gpio_recommended_current_ma": 20,
        # Supply-load model (X6, D2): the run current without radio, as a
        # resistor on the 3.3 V rail: 3.3 V / 80 mA.
        "current_draw_active_ma": 80,
        "supply_model_ohm": 41.0,
        "notes": [
            "3.3V logic — do NOT connect 5V signals without level shifting",
            "GPIO34–39 are input-only; GPIO6–11 are the module's flash",
            "Strapping pins 0, 2, 5, 12, 15 must not be pulled by external circuits",
        ],
    },
    "STM32F411CEU6": {
        "supply_voltage_min": 1.7,
        "supply_voltage_max": 3.6,
        "max_gpio_current_ma": 25,
        "max_total_io_current_ma": 120,
        # Datasheet I/O characteristics: V_OH >= VDD - 1.3 V at |I_IO| = 20 mA
        # -> at most 1.3 / 0.02 = 65 ohm; V_OH >= VDD - 0.4 V at 8 mA (50 ohm).
        # Defeater D7.
        "gpio_output_resistance_ohm": {"min": 20.0, "typ": 35.0, "max": 65.0},
        "gpio_recommended_current_ma": 20,
        # Supply-load model: ~25 mA at 100 MHz, as 3.3 V / 25 mA.
        "current_draw_active_ma": 25,
        "supply_model_ohm": 132.0,
        "notes": [
            "3.3V logic; most pins are 5V-tolerant as inputs only",
            "PC13–PC15 sink at most 3 mA and must not source current",
            "PA11/PA12 are USB; PA13/PA14 are SWD",
        ],
    },
    "SHT31-D": {
        "supply_voltage_min": 2.4,
        "supply_voltage_max": 5.5,
        "current_draw_ma": 1.5,
        "protocol": "I2C",
        "i2c_address_options": ["0x44", "0x45"],
        "required_pullup_on_pins": ["SDA", "SCL"],
        "pullup_value_kohm": 4.7,
        "notes": [
            "I2C protocol. Address: 0x44 (ADDR pin low) or 0x45 (ADDR pin high)",
            "4.7kΩ pull-up on SDA and SCL required",
            "Higher accuracy than DHT22: ±0.3°C, ±2%RH",
        ],
    },
    "DS18B20": {
        "supply_voltage_min": 3.0,
        "supply_voltage_max": 5.5,
        "current_draw_ma": 1.5,
        "protocol": "1-wire",
        "required_pullup_on_pins": ["DATA"],
        "pullup_value_kohm": 4.7,
        "notes": [
            "1-Wire protocol. 4.7kΩ pull-up to VCC on DATA line required",
            "Can operate in parasite-power mode (no separate VCC, draws from data line)",
            "Unique 64-bit serial number — multiple sensors can share one wire",
            "Temperature only: ±0.5°C from -10°C to +85°C",
        ],
    },
    "SIM7070G": {
        "supply_voltage_min": 3.0,
        "supply_voltage_max": 4.2,
        "peak_current_ma": 2000,
        "typical_current_ma": 80,
        "protocol": "AT_commands_via_UART",
        "supported_bands": ["LTE-M", "NB-IoT", "GPRS"],
        "notes": [
            "Peak supply current 2A during transmission — requires large bulk capacitor (100μF+)",
            "Separate 3.3V–4.2V power supply recommended (not from MCU 3.3V rail)",
            "UART interface — baud rate configurable via AT commands",
            "Requires SIM card holder and appropriate antenna",
            "Power on/off via PWRKEY pin",
        ],
    },
    "TP4056": {
        "supply_voltage_input_min": 4.5,
        "supply_voltage_input_max": 8.0,
        "charge_current_max_ma": 1000,
        "charge_current_set_resistor": "R_prog = 1200 / I_charge_mA * 1000 (in Ω)",
        "notes": [
            "LiPo/Li-ion charger IC — do not use with other battery chemistries",
            "Charge current set by Rprog resistor: I_charge = 1200 / Rprog (in mA when Rprog in kΩ)",
            "1.2kΩ Rprog → 1000mA charge current",
            "2.4kΩ Rprog → 500mA charge current",
            "Add protection circuit (DW01A + FS8205A) for cell protection",
        ],
    },
    "LM7805": {
        "supply_voltage_min": 7.0,
        "supply_voltage_max": 35.0,
        "output_voltage": 5.0,
        "max_output_current_ma": 1500,
        "dropout_voltage_min": 2.0,
        "notes": [
            "Linear regulator — dissipates (Vin - 5V) × Iout as heat",
            "At 12V input, 500mA load: power dissipation = 7W — heatsink required",
            "Use buck converter instead when input is >7V or current >200mA to avoid heat",
            "100nF input and output decoupling capacitors required",
        ],
    },
    "AMS1117-3.3": {
        "supply_voltage_min": 4.75,
        "supply_voltage_max": 15.0,
        "output_voltage": 3.3,
        "max_output_current_ma": 1000,
        "dropout_voltage_min": 1.3,
        "notes": [
            "LDO for 3.3V from 5V supply. Dropout = 1.3V — min input = 4.6V",
            "10μF output capacitor required for stability",
            "Max 1A output current",
        ],
    },
    "TPS54360": {
        "supply_voltage_min": 4.5,
        "supply_voltage_max": 60.0,
        "output_voltage_range": "0.8V-60V (set by resistor divider)",
        "max_output_current_ma": 3600,
        "efficiency_typical": "95%",
        "notes": [
            "Buck (step-down) switching regulator — high efficiency",
            "Output voltage set by feedback resistor divider: Vout = 0.8 × (1 + R1/R2)",
            "Requires external inductor (10–47μH) and output capacitor (47–100μF)",
            "Switching frequency 100kHz–2.5MHz — set by RT/CLK pin resistor",
            "Use when input > 7V or output current > 200mA (vs. LDO for low-dropout scenarios)",
        ],
    },
    "PC817": {
        "supply_voltage_max": 35.0,
        "isolation_voltage_v_rms": 5000,
        "current_transfer_ratio_min_pct": 50,
        "led_forward_voltage": 1.2,
        "led_forward_current_max_ma": 50,
        "notes": [
            "Optocoupler for galvanic isolation between field wiring and logic",
            "LED side: 1.2V forward voltage, max 50mA",
            "Calculate LED series resistor: R = (Vin - 1.2) / I_LED",
            "Collector-side pullup resistor sets output high level",
            "For 24VDC digital inputs: R_series = (24 - 1.2) / 0.010 = 2.28kΩ → use 2.2kΩ",
        ],
    },
    "BC547": {
        "supply_voltage_max_vce": 45.0,
        "max_collector_current_ma": 100,
        "hfe_typical": 200,
        "vbe_saturation": 0.7,
        "package": "TO-92",
        "notes": [
            "NPN BJT for switching loads up to 100mA",
            "Base resistor: Rb = (Vlogic - 0.7) / (Ic / hFE × 10) for saturation",
            "For 5V logic driving 50mA load: Rb = (5 - 0.7) / (50/200 × 10) = 1.7kΩ → use 1kΩ",
            "Always add flyback diode across inductive loads (relays, motors)",
        ],
    },
    "1N4007": {
        "max_reverse_voltage": 1000.0,
        "max_forward_current_ma": 1000,
        "forward_voltage": 0.7,
        "notes": [
            "General purpose rectifier diode",
            "Use as flyback diode across relay coils and inductive loads",
            "Cathode band toward positive supply (for flyback: cathode to VCC, anode to coil terminal)",
        ],
    },
    # Everlight red LED used by the LED generator (Stage 3). The diode model in
    # spice.py and predict() are both fitted from these figures: Shockley with
    # ideality `ideality`, saturation current chosen so V_f(test_current) is the
    # typical forward voltage. The min/max bound the tolerance box. Datasheet-
    # derived: defeater D7.
    "67-21URC/S530-A3/TR8": {
        "forward_voltage_v": {"min": 1.7, "typ": 2.0, "max": 2.4},
        "test_current_ma": 20,
        "ideality": 2.0,
        "max_continuous_current_ma": 25,
        "reverse_voltage_max": 5.0,
        "notes": [
            "Red LED, V_f 2.0 V typical (1.7-2.4 V) at 20 mA",
            "25 mA continuous maximum; 5 V reverse maximum",
        ],
    },
    "SMBJ5.0A": {
        "clamping_voltage": 9.2,
        "standoff_voltage": 5.0,
        "max_peak_current_a": 50,
        "notes": [
            "TVS (Transient Voltage Suppressor) diode for surge protection on RS-485 lines",
            "Bidirectional — use on both A and B lines to GND",
            "Clamps voltage spikes from cable induction or ESD to 9.2V",
        ],
    },
}


def get_constraints(part_number: str) -> dict | None:
    """Look up constraints by exact part number. Returns None if unknown."""
    return COMPONENT_CONSTRAINTS.get(part_number)


def format_for_prompt(part_numbers: list[str]) -> str:
    """
    Returns a compact constraint block for injection into the circuit reasoner prompt.
    Only includes entries for the requested parts. Typically 200-500 tokens.
    """
    lines = []
    for pn in part_numbers:
        constraints = get_constraints(pn)
        if constraints:
            lines.append(f"\n### {pn} Constraints")
            for note in constraints.get("notes", []):
                lines.append(f"- {note}")
            if "supply_voltage_max" in constraints:
                lines.append(f"- Max supply voltage: {constraints['supply_voltage_max']}V")
            if "required_pullup_on_pins" in constraints:
                pins = ", ".join(constraints["required_pullup_on_pins"])
                val = constraints.get("pullup_value_kohm", "?")
                to = constraints.get("pullup_to", "VCC")
                lines.append(f"- REQUIRED: {val}kΩ pull-up to {to} on pins: {pins}")
    return "\n".join(lines) if lines else ""
