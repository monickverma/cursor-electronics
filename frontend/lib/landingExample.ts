/**
 * The design the front page lets a visitor poke at before signing in.
 *
 * It is not written for the page: it is the recorded pipeline output for
 * "Arduino Uno driving a status LED at 10 mA" (lib/demo/examples.json, slug
 * `led-indicator`), cut down to the fields the schematic drawing reads. The
 * justifications are the generator's own sentences, unedited.
 */
export const LANDING_PROMPT = 'Arduino Uno driving a status LED at 10 mA'

export const LANDING_IR = {
  components: [
    {
      id: 'U1', type: 'microcontroller', value: null, part_number: 'ATmega328P-PU',
      manufacturer: 'Microchip', package: 'DIP-28',
      justification: 'Arduino Uno MCU driving the LED from D13. Each GPIO is rated 20 mA recommended, 40 mA absolute; this design stays at or under 11.7 mA over every part tolerance.',
    },
    {
      id: 'LED1', type: 'led', value: null, part_number: '150080RS75000',
      manufacturer: 'Würth Elektronik', package: '0805',
      justification: 'Red LED, V_f 1.96 V at 9.95 mA on its fitted diode model (datasheet 1.7–2.4 V at 20 mA). A lower-V_f part in the same spread raises the current to 11.7 mA — still under its 30 mA rating.',
    },
    {
      id: 'R1', type: 'resistor', value: '280', part_number: 'RC0402FR-07280RL',
      manufacturer: 'Yageo', package: '0402',
      justification: '280Ω, the E96 value nearest 10 mA. It sets I = (V_pin − V_f)/R1 ≈ 9.95 mA; halving it would roughly double the current and, past 20 mA, overload the pin.',
    },
    {
      id: 'C1', type: 'capacitor', value: '100nF', part_number: 'CL05B104KO5NNNC',
      manufacturer: 'Samsung', package: '0402',
      justification: "100nF X7R bypass on U1's supply pin, placed close to it. It supplies the fast edges the rail's trace inductance cannot; without it switching noise couples into every line on the board. Rated 16 V against the 5 V rail.",
    },
  ],
  nodes: [
    { id: 'VCC_5V', type: 'power', voltage_nominal: 5.0 },
    { id: 'GND', type: 'ground', voltage_nominal: 0.0 },
    { id: 'LED_CTRL', type: 'digital', voltage_nominal: 5.0 },
    { id: 'LED_ANODE', type: 'digital', voltage_nominal: null },
  ],
  connections: [
    { component_id: 'U1', pin: 'VCC', node_id: 'VCC_5V', direction: 'input' },
    { component_id: 'U1', pin: 'GND', node_id: 'GND', direction: 'input' },
    { component_id: 'C1', pin: '+', node_id: 'VCC_5V', direction: 'bidirectional' },
    { component_id: 'C1', pin: '-', node_id: 'GND', direction: 'bidirectional' },
    { component_id: 'U1', pin: 'D13', node_id: 'LED_CTRL', direction: 'output' },
    { component_id: 'R1', pin: 'A', node_id: 'LED_CTRL', direction: 'bidirectional' },
    { component_id: 'R1', pin: 'B', node_id: 'LED_ANODE', direction: 'bidirectional' },
    { component_id: 'LED1', pin: 'ANODE', node_id: 'LED_ANODE', direction: 'input' },
    { component_id: 'LED1', pin: 'CATHODE', node_id: 'GND', direction: 'input' },
  ],
}
