"""
Five canonical example IRs used for testing every downstream module.
All 5 must instantiate cleanly and pass IR validation before any other code is written.
"""

from .ir_schema import (
    ApplicationClass, CircuitIR, Component, ComponentType,
    Connection, Node, SafetyClass, SignalType,
    SimulationAnalysis, SimulationSpec, ValidationRule,
)

# IR_001: Arduino Uno + DHT22 temperature/humidity sensor with threshold alert
IR_001 = CircuitIR(
    intent="Temperature and humidity monitoring with relay alert above 40°C",
    application_class=ApplicationClass.HOBBY_ARDUINO,
    safety_class=SafetyClass.GENERAL,
    target_mcu="arduino_uno",
    components=[
        Component(
            id="U1", type=ComponentType.MICROCONTROLLER,
            part_number="ATmega328P-PU", manufacturer="Microchip", package="DIP-28",
            supply_voltage_min=1.8, supply_voltage_max=5.5, current_draw_ma=50,
            operating_temp_min=-40, operating_temp_max=85,
            confidence=0.97,
            justification="Arduino Uno MCU. 5V logic, 32KB flash, hardware UART for debug, "
                          "14 digital I/O, 6 analog inputs. Standard choice for hobbyist sensor nodes.",
            lcsc_pn="C14877",
        ),
        Component(
            id="U2", type=ComponentType.SENSOR, sensor_type="dht22",
            part_number="DHT22", manufacturer="Aosong", package="4-pin SIP",
            supply_voltage_min=3.3, supply_voltage_max=5.5, current_draw_ma=2.5,
            operating_temp_min=-40, operating_temp_max=80,
            confidence=0.92,
            justification="DHT22 provides both temperature (±0.5°C) and humidity (±2%RH) via "
                          "single-wire digital protocol. Requires 10kΩ pull-up on DATA pin per datasheet §4.2.",
            lcsc_pn="C19528",
            datasheet_notes=["DATA pin requires 10kΩ pull-up to VCC", "Min 2s between readings"],
        ),
        Component(
            id="R1", type=ComponentType.RESISTOR,
            part_number="RC0402FR-0710KL", manufacturer="Yageo", package="0402",
            value="10k", supply_voltage_max=50, current_draw_ma=0.5,
            confidence=0.99,
            justification="10kΩ pull-up on DHT22 DATA line. Required by Aosong datasheet. "
                          "Value must be 5kΩ–10kΩ at 3.3V–5V supply.",
            lcsc_pn="C25744",
        ),
        Component(
            id="C1", type=ComponentType.CAPACITOR,
            part_number="CL05B104KO5NNNC", manufacturer="Samsung", package="0402",
            value="100nF", supply_voltage_max=16, current_draw_ma=0,
            confidence=0.99,
            justification="100nF decoupling capacitor on U1 VCC pin. Filters high-frequency noise "
                          "on power rail. Standard practice per AVR hardware design guide.",
            lcsc_pn="C1525",
        ),
    ],
    nodes=[
        Node(id="VCC_5V", voltage_nominal=5.0, type=SignalType.POWER),
        Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
        Node(id="DHT22_DATA", type=SignalType.ONE_WIRE, protocol="dht_single_wire"),
    ],
    connections=[
        Connection(component_id="U1", pin="VCC", node_id="VCC_5V", direction="input"),
        Connection(component_id="U1", pin="GND", node_id="GND", direction="input"),
        Connection(component_id="U1", pin="D2", node_id="DHT22_DATA", direction="bidirectional"),
        Connection(component_id="U2", pin="VCC", node_id="VCC_5V", direction="input"),
        Connection(component_id="U2", pin="GND", node_id="GND", direction="input"),
        Connection(component_id="U2", pin="DATA", node_id="DHT22_DATA", direction="output"),
        Connection(component_id="R1", pin="A", node_id="VCC_5V"),
        Connection(component_id="R1", pin="B", node_id="DHT22_DATA"),
        Connection(component_id="C1", pin="+", node_id="VCC_5V"),
        Connection(component_id="C1", pin="-", node_id="GND"),
    ],
    constraints={
        "supply_voltage": 5.0,
        "supply_current_ma": 500,
        "threshold_temp_celsius": 40,
    },
    simulation_spec=SimulationSpec(
        analyses=[SimulationAnalysis(type="dc_op", description="Verify 5V rail at nominal load")],
        expected_outputs={"VCC_5V": 5.0},
    ),
    validation_rules=[
        ValidationRule.NO_FLOATING_NODES,
        ValidationRule.VOLTAGE_RATINGS_OK,
        ValidationRule.PULLUP_ON_OPEN_DRAIN,
        ValidationRule.POWER_SUPPLY_ADEQUATE,
    ],
)

# IR_002: Arduino Uno + LED with current-limiting resistor
IR_002 = CircuitIR(
    intent="Drive an LED from Arduino GPIO with current limiting",
    application_class=ApplicationClass.HOBBY_ARDUINO,
    target_mcu="arduino_uno",
    components=[
        Component(
            id="U1", type=ComponentType.MICROCONTROLLER,
            part_number="ATmega328P-PU", manufacturer="Microchip", package="DIP-28",
            supply_voltage_min=1.8, supply_voltage_max=5.5, current_draw_ma=50,
            confidence=0.97,
            justification="Arduino Uno MCU. GPIO pins source/sink max 40mA per pin, 200mA total.",
            lcsc_pn="C14877",
        ),
        Component(
            id="LED1", type=ComponentType.LED,
            part_number="67-21URC/S530-A3/TR8", manufacturer="Everlight", package="0805",
            supply_voltage_max=5.0, current_draw_ma=20,
            confidence=0.85,
            justification="Standard red LED in 0805 package. Forward voltage 2.0V at 20mA. "
                          "Current limited by R1 (150Ω): I = (5V - 2.0V) / 150Ω = 20mA. "
                          "Reverse breakdown 5V — safe in 5V system.",
            lcsc_pn="C72038",
            datasheet_notes=["Forward voltage Vf=2.0V at 20mA", "Max reverse voltage 5V"],
        ),
        Component(
            id="C1", type=ComponentType.CAPACITOR,
            part_number="CL05B104KO5NNNC", manufacturer="Samsung", package="0402",
            value="100nF", supply_voltage_max=16,
            confidence=0.99,
            justification="Decoupling capacitor on MCU VCC pin. Filters high-frequency "
                          "noise on 5V power rail per AVR hardware design guidelines.",
            lcsc_pn="C1525",
        ),
        Component(
            id="R1", type=ComponentType.RESISTOR,
            part_number="RC0402FR-07150RL", manufacturer="Yageo", package="0402",
            value="150R", supply_voltage_max=50, current_draw_ma=20,
            confidence=0.99,
            justification="150Ω current-limiting resistor. R = (VCC - Vf) / If = "
                          "(5V - 2.0V) / 0.020A = 150Ω. Limits LED current to 20mA, "
                          "within Arduino GPIO sink limit of 40mA.",
            lcsc_pn="C25071",
        ),
    ],
    nodes=[
        Node(id="VCC_5V", voltage_nominal=5.0, type=SignalType.POWER),
        Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
        Node(id="LED_CTRL", type=SignalType.DIGITAL),
        Node(id="LED_ANODE", type=SignalType.DIGITAL),
    ],
    connections=[
        Connection(component_id="U1", pin="VCC", node_id="VCC_5V", direction="input"),
        Connection(component_id="U1", pin="GND", node_id="GND", direction="input"),
        Connection(component_id="U1", pin="D13", node_id="LED_CTRL", direction="output"),
        Connection(component_id="R1", pin="A", node_id="LED_CTRL"),
        Connection(component_id="R1", pin="B", node_id="LED_ANODE"),
        Connection(component_id="LED1", pin="ANODE", node_id="LED_ANODE", direction="input"),
        Connection(component_id="LED1", pin="CATHODE", node_id="GND", direction="input"),
        Connection(component_id="C1", pin="+", node_id="VCC_5V"),
        Connection(component_id="C1", pin="-", node_id="GND"),
    ],
    constraints={"supply_voltage": 5.0},
    simulation_spec=SimulationSpec(
        analyses=[SimulationAnalysis(type="dc_op", description="Verify LED current at 5V supply")],
        expected_outputs={"LED_ANODE": 2.0},
    ),
    validation_rules=[
        ValidationRule.NO_FLOATING_NODES,
        ValidationRule.VOLTAGE_RATINGS_OK,
        ValidationRule.CURRENT_LIMITS_OK,
    ],
)

# IR_003: RC low-pass filter, 1kHz cutoff
IR_003 = CircuitIR(
    intent="RC low-pass filter with 1kHz cutoff frequency",
    application_class=ApplicationClass.HOBBY_ARDUINO,
    components=[
        Component(
            id="R1", type=ComponentType.RESISTOR,
            part_number="RC0402FR-071K59L", manufacturer="Yageo", package="0402",
            value="1k59", supply_voltage_max=50,
            confidence=0.99,
            justification="1.59kΩ resistor (E24 nearest to 1590Ω). With C1=100nF gives "
                          "cutoff f = 1/(2π×1590×100e-9) = 1001Hz ≈ 1kHz.",
            lcsc_pn="C25867",
        ),
        Component(
            id="C1", type=ComponentType.CAPACITOR,
            part_number="CL05B104KO5NNNC", manufacturer="Samsung", package="0402",
            value="100nF", supply_voltage_max=16,
            confidence=0.99,
            justification="100nF ceramic capacitor (C0G/NP0 dielectric for frequency stability). "
                          "Forms RC filter with R1=1.59kΩ for 1kHz cutoff.",
            lcsc_pn="C1525",
        ),
    ],
    nodes=[
        Node(id="IN", voltage_nominal=5.0, type=SignalType.ANALOG),
        Node(id="OUT", type=SignalType.ANALOG),
        Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
    ],
    connections=[
        Connection(component_id="R1", pin="A", node_id="IN"),
        Connection(component_id="R1", pin="B", node_id="OUT"),
        Connection(component_id="C1", pin="+", node_id="OUT"),
        Connection(component_id="C1", pin="-", node_id="GND"),
    ],
    constraints={"supply_voltage": 5.0, "cutoff_hz": 1000},
    simulation_spec=SimulationSpec(
        analyses=[
            SimulationAnalysis(
                type="ac_sweep", description="Verify -3dB cutoff at 1kHz",
                f_start=10.0, f_stop=100000.0, points_per_decade=20,
            )
        ],
        expected_outputs={"OUT": 3.536},  # -3dB from 5V = 5 * 0.707 = 3.535V
    ),
    validation_rules=[ValidationRule.NO_FLOATING_NODES, ValidationRule.VOLTAGE_RATINGS_OK],
)

# IR_004: Voltage divider (12V → 5V output)
IR_004 = CircuitIR(
    intent="Voltage divider stepping 12V down to approximately 5V",
    application_class=ApplicationClass.HOBBY_ARDUINO,
    components=[
        Component(
            id="R1", type=ComponentType.RESISTOR,
            part_number="RC0402FR-077KL", manufacturer="Yageo", package="0402",
            value="7k", supply_voltage_max=50,
            confidence=0.95,
            justification="Upper resistor of divider. R1=7kΩ, R2=5kΩ → Vout = 12 × 5/(7+5) = 5V. "
                          "High-impedance divider, not suitable for supplying load current >1mA.",
            lcsc_pn="C25946",
        ),
        Component(
            id="R2", type=ComponentType.RESISTOR,
            part_number="RC0402FR-075KL", manufacturer="Yageo", package="0402",
            value="5k1", supply_voltage_max=50,
            confidence=0.95,
            justification="Lower resistor of divider. 5.1kΩ (E24 nearest to 5kΩ). "
                          "Actual Vout = 12 × 5.1/(7.0+5.1) = 5.07V ≈ 5V.",
            lcsc_pn="C25905",
        ),
    ],
    nodes=[
        Node(id="VIN_12V", voltage_nominal=12.0, type=SignalType.POWER),
        Node(id="VOUT_5V", voltage_nominal=5.0, type=SignalType.ANALOG),
        Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
    ],
    connections=[
        Connection(component_id="R1", pin="A", node_id="VIN_12V"),
        Connection(component_id="R1", pin="B", node_id="VOUT_5V"),
        Connection(component_id="R2", pin="A", node_id="VOUT_5V"),
        Connection(component_id="R2", pin="B", node_id="GND"),
    ],
    constraints={"supply_voltage": 12.0},
    simulation_spec=SimulationSpec(
        analyses=[SimulationAnalysis(type="dc_op", description="Verify output at 5V")],
        expected_outputs={"VOUT_5V": 5.07},
    ),
    validation_rules=[ValidationRule.NO_FLOATING_NODES, ValidationRule.VOLTAGE_RATINGS_OK],
)

# IR_005: Arduino Uno + MAX485 (RS-485 / Modbus RTU interface)
IR_005 = CircuitIR(
    intent="Arduino Uno with MAX485 RS-485 transceiver for Modbus RTU master",
    application_class=ApplicationClass.MODBUS_RTU,
    target_mcu="arduino_uno",
    components=[
        Component(
            id="U1", type=ComponentType.MICROCONTROLLER,
            part_number="ATmega328P-PU", manufacturer="Microchip", package="DIP-28",
            supply_voltage_min=1.8, supply_voltage_max=5.5, current_draw_ma=50,
            confidence=0.97,
            justification="Arduino Uno MCU. Hardware Serial1 used for RS-485 Modbus, "
                          "Serial0 for debug. GPIO D2 drives DE/RE enable pin.",
            lcsc_pn="C14877",
        ),
        Component(
            id="U2", type=ComponentType.TRANSCEIVER,
            part_number="MAX485ECSA", manufacturer="Maxim", package="SOIC-8",
            supply_voltage_min=4.75, supply_voltage_max=5.25, current_draw_ma=0.3,
            confidence=0.96,
            justification="MAX485 half-duplex RS-485 transceiver. Industry standard for Modbus RTU. "
                          "DE and RE pins tied together, driven by single Arduino GPIO for direction control. "
                          "Operating temp -40°C to +85°C.",
            lcsc_pn="C6456",
            datasheet_notes=["DE and RE must be tied together", "120Ω termination required at bus endpoints"],
        ),
        Component(
            id="R1", type=ComponentType.RESISTOR,
            part_number="RC0402FR-07120RL", manufacturer="Yageo", package="0402",
            value="120R", supply_voltage_max=50,
            confidence=0.99,
            justification="120Ω termination resistor between RS-485 A and B lines. "
                          "Matches characteristic impedance of RS-485 cable (120Ω). "
                          "Required at both ends of bus to prevent signal reflections.",
            lcsc_pn="C25071",
        ),
        Component(
            id="R2", type=ComponentType.RESISTOR,
            part_number="RC0402FR-07560RL", manufacturer="Yageo", package="0402",
            value="560R", supply_voltage_max=50,
            confidence=0.92,
            justification="RS-485 A-line bias resistor to VCC. Ensures bus stays in defined state "
                          "when all transmitters are tri-stated. 560Ω standard value per RS-485 spec.",
            lcsc_pn="C23216",
        ),
        Component(
            id="R3", type=ComponentType.RESISTOR,
            part_number="RC0402FR-07560RL", manufacturer="Yageo", package="0402",
            value="560R", supply_voltage_max=50,
            confidence=0.92,
            justification="RS-485 B-line bias resistor to GND. Paired with R2 to bias bus. "
                          "Both bias resistors are required for reliable idle-state detection.",
            lcsc_pn="C23216",
        ),
        Component(
            id="C1", type=ComponentType.CAPACITOR,
            part_number="CL05B104KO5NNNC", manufacturer="Samsung", package="0402",
            value="100nF", supply_voltage_max=16,
            confidence=0.99,
            justification="Decoupling capacitor on MAX485 VCC pin. Suppresses transient current "
                          "during transmit/receive switching.",
            lcsc_pn="C1525",
        ),
    ],
    nodes=[
        Node(id="VCC_5V", voltage_nominal=5.0, type=SignalType.POWER),
        Node(id="GND", voltage_nominal=0.0, type=SignalType.GROUND),
        Node(id="UART_TX", type=SignalType.UART_TX, protocol="UART"),
        Node(id="UART_RX", type=SignalType.UART_RX, protocol="UART"),
        Node(id="RS485_DE_RE", type=SignalType.DIGITAL),
        Node(id="RS485_A", type=SignalType.RS485_A, protocol="RS485"),
        Node(id="RS485_B", type=SignalType.RS485_B, protocol="RS485"),
    ],
    connections=[
        Connection(component_id="U1", pin="VCC", node_id="VCC_5V", direction="input"),
        Connection(component_id="U1", pin="GND", node_id="GND", direction="input"),
        Connection(component_id="U1", pin="D1_TX", node_id="UART_TX", direction="output"),
        Connection(component_id="U1", pin="D0_RX", node_id="UART_RX", direction="input"),
        Connection(component_id="U1", pin="D2", node_id="RS485_DE_RE", direction="output"),
        Connection(component_id="U2", pin="VCC", node_id="VCC_5V", direction="input"),
        Connection(component_id="U2", pin="GND", node_id="GND", direction="input"),
        Connection(component_id="U2", pin="DI", node_id="UART_TX", direction="input"),
        Connection(component_id="U2", pin="RO", node_id="UART_RX", direction="output"),
        Connection(component_id="U2", pin="DE", node_id="RS485_DE_RE", direction="input"),
        Connection(component_id="U2", pin="RE", node_id="RS485_DE_RE", direction="input"),
        Connection(component_id="U2", pin="A", node_id="RS485_A", direction="output"),
        Connection(component_id="U2", pin="B", node_id="RS485_B", direction="output"),
        Connection(component_id="R1", pin="A", node_id="RS485_A"),
        Connection(component_id="R1", pin="B", node_id="RS485_B"),
        Connection(component_id="R2", pin="A", node_id="VCC_5V"),
        Connection(component_id="R2", pin="B", node_id="RS485_A"),
        Connection(component_id="R3", pin="A", node_id="RS485_B"),
        Connection(component_id="R3", pin="B", node_id="GND"),
        Connection(component_id="C1", pin="+", node_id="VCC_5V"),
        Connection(component_id="C1", pin="-", node_id="GND"),
    ],
    constraints={
        "supply_voltage": 5.0,
        "supply_current_ma": 500,
        "modbus_baud": 9600,
        "modbus_slaves": [
            {"address": 1, "register_start": 0, "register_count": 4, "name": "Device_1"},
            {"address": 2, "register_start": 0, "register_count": 4, "name": "Device_2"},
        ],
        "poll_interval_ms": 5000,
    },
    simulation_spec=SimulationSpec(
        analyses=[SimulationAnalysis(type="dc_op", description="Verify 5V rail and MAX485 supply")],
        expected_outputs={"VCC_5V": 5.0},
    ),
    validation_rules=[
        ValidationRule.NO_FLOATING_NODES,
        ValidationRule.VOLTAGE_RATINGS_OK,
        ValidationRule.RS485_TERMINATION_PRESENT,
        ValidationRule.RS485_BIAS_RESISTORS,
        ValidationRule.POWER_SUPPLY_ADEQUATE,
    ],
)

ALL_EXAMPLES = [IR_001, IR_002, IR_003, IR_004, IR_005]
