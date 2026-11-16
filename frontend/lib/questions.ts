/**
 * The backend names a missing value by its path in the requirement
 * (`blocks.climate.constraints.cable_length_m`). That is exact, and it is not a
 * question anyone can read. This turns the path into the question, and keeps the
 * path beside it: the path is what the reply is matched against, and what a bug
 * report needs.
 *
 * The wording is presentation only. Which values are missing is still decided
 * by the backend's generators, and the answer still goes back as the person's
 * own words added to their request.
 */

// The fields the generators can ask for today (grep of backend/generators, 2026-11-16).
const ASK: Record<string, string> = {
  supply_v: 'What supply voltage does it run from, in volts?',
  supply_current_ma: 'How much current can the supply give, in mA?',
  cable_length_m: 'How long is the cable, in metres?',
  load_current_ma: 'How much current does the load draw, in mA?',
  led_current_ma: 'How much current should the LED get, in mA?',
  cutoff_hz: 'What cutoff frequency do you want, in Hz?',
  tolerance_pct: 'How close does it need to be, as a percentage?',
  baud: 'What baud rate?',
  far_end_terminated: 'Is the far end of the bus terminated? (yes or no)',
  load_inductive: 'Is the load inductive, like a relay or a motor? (yes or no)',
  source_impedance_ohm: 'What is the impedance of whatever drives it, in ohms?',
}

// A field this file has not met: read its unit off its name rather than show a bare path.
const UNITS: [RegExp, string][] = [
  [/_ma$/, 'in mA'], [/_v$/, 'in volts'], [/_hz$/, 'in Hz'], [/_ohm$/, 'in ohms'],
  [/_pct$/, 'as a percentage'], [/_ms$/, 'in ms'], [/_m$/, 'in metres'], [/_c$/, 'in °C'], [/_s$/, 'in seconds'],
]

export function plainQuestion(path: string): string {
  const parts = path.split('.')
  const key = parts[parts.length - 1]
  // blocks.<name>.<...>: the design has several blocks, so say which one is asking.
  const block = parts[0] === 'blocks' && parts.length > 2 ? parts[1] : null

  let question = ASK[key]
  if (!question) {
    const unit = UNITS.find(([suffix]) => suffix.test(key))
    const words = (unit ? key.replace(unit[0], '') : key).replace(/_/g, ' ').trim()
    question = `What is the ${words || key}${unit ? `, ${unit[1]}` : ''}?`
  }
  return block ? `For the ${block.replace(/_/g, ' ')} block: ${question}` : question
}

/** The whole message for a request that left values out. */
export function missingValuesMessage(paths: string[]): string {
  const n = paths.length
  return [
    `I need ${n === 1 ? 'one more value' : `${n} more values`} before I can build this:`,
    ...paths.map(p => `  • ${plainQuestion(p)}  [${p}]`),
    'Reply with the missing values and I will add them to your request.',
  ].join('\n')
}
