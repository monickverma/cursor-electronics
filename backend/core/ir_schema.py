from __future__ import annotations

import uuid
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ComponentType(str, Enum):
    MICROCONTROLLER = "microcontroller"
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    LED = "led"
    SENSOR = "sensor"
    RELAY = "relay"
    TRANSISTOR = "transistor"
    REGULATOR = "regulator"
    TRANSCEIVER = "transceiver"
    MODEM = "modem"
    CONNECTOR = "connector"
    CRYSTAL = "crystal"
    DIODE = "diode"
    INDUCTOR = "inductor"
    OPAMP = "opamp"
    OPTOCOUPLER = "optocoupler"


class SignalType(str, Enum):
    POWER = "power"
    GROUND = "ground"
    DIGITAL = "digital"
    ANALOG = "analog"
    I2C_SDA = "i2c_sda"
    I2C_SCL = "i2c_scl"
    SPI_MOSI = "spi_mosi"
    SPI_MISO = "spi_miso"
    SPI_SCK = "spi_sck"
    SPI_CS = "spi_cs"
    UART_TX = "uart_tx"
    UART_RX = "uart_rx"
    RS485_A = "rs485_a"
    RS485_B = "rs485_b"
    PWM = "pwm"
    ONE_WIRE = "one_wire"


class ApplicationClass(str, Enum):
    HOBBY_ARDUINO = "hobby_arduino"
    IOT_NODE = "iot_node"
    INDUSTRIAL_IO = "industrial_io"
    HVAC_CONTROL = "hvac_control"
    MODBUS_RTU = "modbus_rtu"


class SafetyClass(str, Enum):
    GENERAL = "general"
    INDUSTRIAL = "industrial"
    LIFE_SAFETY = "life_safety"


class ValidationRule(str, Enum):
    NO_FLOATING_NODES = "no_floating_nodes"
    VOLTAGE_RATINGS_OK = "voltage_ratings_ok"
    CURRENT_LIMITS_OK = "current_limits_ok"
    I2C_PULLUPS_PRESENT = "i2c_pullups_present"
    RS485_TERMINATION_PRESENT = "rs485_termination_present"
    RS485_BIAS_RESISTORS = "rs485_bias_resistors"
    PWM_PIN_VALID = "pwm_pin_valid"
    OPERATING_TEMP_RANGE = "operating_temp_range"
    POWER_SUPPLY_ADEQUATE = "power_supply_adequate"
    PULLUP_ON_OPEN_DRAIN = "pullup_on_open_drain"


class Component(BaseModel):
    id: str                                        # R1, C1, U1 — sequential within type
    type: ComponentType
    part_number: str                               # Exact manufacturer part number
    manufacturer: str
    package: str                                   # 0402, DIP-28, SOT-23, etc.
    value: Optional[str] = None                    # "10k", "100nF", "1uH" — passives only
    lcsc_pn: Optional[str] = None
    digikey_pn: Optional[str] = None
    supply_voltage_min: Optional[float] = None
    supply_voltage_max: Optional[float] = None
    current_draw_ma: Optional[float] = None
    operating_temp_min: Optional[float] = None
    operating_temp_max: Optional[float] = None
    sensor_type: Optional[str] = None             # "dht22", "bmp280", "ds18b20"
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str = Field(min_length=20)
    datasheet_notes: List[str] = []

    @field_validator("justification")
    @classmethod
    def justification_must_explain(cls, v: str) -> str:
        if len(v.strip()) < 20:
            raise ValueError("justification must be at least 20 characters — explain the WHY")
        return v


class Node(BaseModel):
    id: str                                        # "VCC_3V3", "GND", "SDA_BUS"
    voltage_nominal: Optional[float] = None
    type: SignalType
    protocol: Optional[str] = None                # "I2C", "SPI", "MODBUS_RTU"
    frequency_hz: Optional[float] = None


class Connection(BaseModel):
    component_id: str                              # References Component.id
    pin: str                                       # Pin name as on the datasheet
    node_id: str                                   # References Node.id
    direction: Literal["input", "output", "bidirectional"] = "bidirectional"


class SimulationAnalysis(BaseModel):
    type: Literal["dc_op", "ac_sweep", "transient"]
    description: str
    f_start: Optional[float] = None               # Hz — for ac_sweep
    f_stop: Optional[float] = None                # Hz — for ac_sweep
    points_per_decade: Optional[int] = None
    stop_time: Optional[str] = None               # e.g. "10ms" — for transient
    step_time: Optional[str] = None               # e.g. "0.1ms" — for transient


class SimulationSpec(BaseModel):
    analyses: List[SimulationAnalysis]
    expected_outputs: Dict[str, float] = {}        # node_id → expected voltage


class PatchRecord(BaseModel):
    version: int
    change_summary: str
    changed_component_ids: List[str]
    timestamp: str
    prompted_by: str


class CircuitIR(BaseModel):
    circuit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    intent: str                                    # Original user prompt
    # "name@version" of the generator that realised this design (v2 §6).
    # Stamped by generators/realize.py; None on designs built before Stage 2.
    generator: Optional[str] = None
    application_class: ApplicationClass
    safety_class: SafetyClass = SafetyClass.GENERAL
    target_mcu: Optional[str] = None              # "arduino_uno", "esp32", "stm32f4"

    components: List[Component]
    nodes: List[Node]
    connections: List[Connection]

    constraints: Dict = {}
    simulation_spec: Optional[SimulationSpec] = None
    validation_rules: List[ValidationRule]

    patch_history: List[PatchRecord] = []

    # Populated after pipeline runs
    simulation_passed: Optional[bool] = None
    simulation_results: Optional[Dict] = None
    validation_results: Optional[Dict] = None

    @field_validator("components")
    @classmethod
    def component_ids_unique(cls, v: List[Component]) -> List[Component]:
        ids = [c.id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("All component IDs must be unique")
        return v

    @field_validator("connections")
    @classmethod
    def connections_reference_valid_ids(cls, v: List[Connection], info) -> List[Connection]:
        # Validate that component_id references exist (when components are set)
        # Full cross-field validation done in ir_validator.py
        return v

    model_config = ConfigDict(use_enum_values=True)
