/*
 * RC time constant on an Arduino Uno, without a signal generator — defeater D1.
 * docs/BENCH_D1.md, "The RC filter without a signal generator".
 *
 *   D12 ──(drive)── IN ── R1 ──┬── OUT ── D6 (AIN0, comparator +)
 *                              C1
 *                              │
 *                             GND
 *   5V ── Ra ──┬── Rb ── GND     A0 = k1·5V  (lower threshold, ~1/3)
 *   5V ── Rc ──┬── Rd ── GND     A1 = k2·5V  (upper threshold, ~2/3)
 *
 * A step on IN charges C1 as v(t) = V·(1 − e^(−t/RC)). The comparator (AIN0
 * against A0, then A1, chosen through the ADC multiplexer with ACME) captures
 * the moment OUT crosses each threshold in Timer1 (62.5 ns a tick at 16 MHz).
 * The difference of the two crossing times does not depend on any fixed delay
 * — the port write, the comparator's propagation time, the capture logic —
 * so
 *
 *     t2 − t1 = RC · ln((1 − k1) / (1 − k2))
 *
 * Measure k1 and k2 with the meter (V(A0)/V(5V), V(A1)/V(5V)) and enter them
 * below, or recompute from the printed times. The pin's own output resistance
 * (≈ 25 Ω) is in series with R1: record it in the accuracy, or pick R1 in
 * kilohms where it is under 1 %.
 *
 * Serial at 115200: one line per run of RUNS captures per threshold, then
 * t1, t2, RC and f_c = 1 / (2π·RC). Send 'r' to measure again.
 */
#include <Arduino.h>
#include <math.h>

// ── Set these to the ratios you measured ─────────────────────────────────────
static const float K1 = 1.0f / 3.0f;   // V(A0) / V(5V)
static const float K2 = 2.0f / 3.0f;   // V(A1) / V(5V)
static const uint16_t RUNS = 200;      // captures per threshold (the sheet asks for ≥ 100)
// ─────────────────────────────────────────────────────────────────────────────

static const uint8_t DRIVE_BIT = PB4;  // D12
static volatile uint16_t overflows;
static volatile uint32_t captured;
static volatile bool done;

ISR(TIMER1_OVF_vect) { overflows++; }

ISR(TIMER1_CAPT_vect) {
  uint16_t icr = ICR1;
  uint16_t ovf = overflows;
  // An overflow that landed just before the capture but was not serviced yet.
  if ((TIFR1 & _BV(TOV1)) && icr < 0x8000) ovf++;
  captured = ((uint32_t)ovf << 16) | icr;
  done = true;
  TIMSK1 &= ~_BV(ICIE1);
}

static void select_threshold(uint8_t adc_channel) {
  ADCSRA &= ~_BV(ADEN);                       // the multiplexer feeds the comparator only with the ADC off
  ADCSRB |= _BV(ACME);
  ADMUX = (ADMUX & 0xF0) | (adc_channel & 0x07);
  delayMicroseconds(50);
}

static void discharge(uint32_t us) {
  PORTB &= ~_BV(DRIVE_BIT);
  while (us > 16000) { delayMicroseconds(16000); us -= 16000; }
  delayMicroseconds(us);
}

// Ticks from the drive edge to the comparator's rising edge; 0 on a timeout.
static uint32_t one_capture(uint32_t timeout_ticks) {
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  overflows = 0;
  done = false;
  TIFR1 = _BV(ICF1) | _BV(TOV1);               // clear stale flags
  TIMSK1 = _BV(ICIE1) | _BV(TOIE1);
  // Rising edge of the comparator output (OUT climbing past the threshold),
  // noise canceller on (a constant 4-clock delay; it cancels in t2 − t1).
  TCCR1B = _BV(ICNC1) | _BV(ICES1) | _BV(CS10);
  PORTB |= _BV(DRIVE_BIT);                     // the step, one cycle after the timer starts
  interrupts();
  while (!done) {
    noInterrupts();
    uint32_t now = ((uint32_t)overflows << 16) | TCNT1;
    interrupts();
    if (now > timeout_ticks) break;
  }
  TCCR1B = 0;
  TIMSK1 = 0;
  return done ? captured : 0;
}

struct Stats { double mean_ticks; double sd_ticks; uint16_t n; };

static Stats measure(uint8_t channel, uint32_t discharge_us, uint32_t timeout_ticks) {
  select_threshold(channel);
  double sum = 0, sum2 = 0;
  uint16_t n = 0;
  for (uint16_t i = 0; i < RUNS; i++) {
    discharge(discharge_us);
    uint32_t t = one_capture(timeout_ticks);
    if (t == 0) continue;
    sum += t;
    sum2 += (double)t * t;
    n++;
  }
  Stats s = {0, 0, n};
  if (n > 1) {
    s.mean_ticks = sum / n;
    s.sd_ticks = sqrt((sum2 - sum * sum / n) / (n - 1));
  }
  return s;
}

static void run() {
  // First pass, generous: find the scale, then discharge for 20× the upper crossing.
  const uint32_t timeout = 16000000UL;         // 1 s
  select_threshold(1);
  discharge(200000);
  uint32_t probe = one_capture(timeout);
  if (probe == 0) {
    Serial.println(F("no crossing within 1 s: check the wiring (OUT on D6, thresholds on A0/A1, drive on D12)"));
    return;
  }
  uint32_t discharge_us = max((uint32_t)2000, (uint32_t)(probe / 16UL) * 20UL);
  uint32_t limit = probe * 4UL + 1600UL;
  Stats lo = measure(0, discharge_us, limit);
  Stats hi = measure(1, discharge_us, limit);
  if (lo.n < 2 || hi.n < 2) {
    Serial.println(F("too few captures: is A0 below A1, and both between 0 and 5 V?"));
    return;
  }
  const double tick_us = 1e6 / F_CPU;
  double t1 = lo.mean_ticks * tick_us, t2 = hi.mean_ticks * tick_us;
  double rc = (t2 - t1) / log((1.0 - K1) / (1.0 - K2));   // µs
  double fc = 1e6 / (2.0 * M_PI * rc);
  Serial.print(F("t1 = ")); Serial.print(t1, 3); Serial.print(F(" us (sd ")); Serial.print(lo.sd_ticks * tick_us, 3);
  Serial.print(F(", n ")); Serial.print(lo.n); Serial.print(F(")   t2 = ")); Serial.print(t2, 3);
  Serial.print(F(" us (sd ")); Serial.print(hi.sd_ticks * tick_us, 3); Serial.print(F(", n ")); Serial.print(hi.n);
  Serial.println(F(")"));
  Serial.print(F("k1 = ")); Serial.print(K1, 4); Serial.print(F("  k2 = ")); Serial.print(K2, 4);
  Serial.print(F("   RC = ")); Serial.print(rc, 3); Serial.print(F(" us   f_c = ")); Serial.print(fc, 2);
  Serial.println(F(" Hz"));
}

void setup() {
  Serial.begin(115200);
  DDRB |= _BV(DRIVE_BIT);
  PORTB &= ~_BV(DRIVE_BIT);
  DIDR1 = _BV(AIN0D);                           // D6 is analog: no digital input buffer
  ACSR = _BV(ACIC);                             // comparator → Timer1 input capture, bandgap off
  Serial.println(F("rc_timer: RC from two comparator thresholds (docs/BENCH_D1.md). 'r' repeats."));
  run();
}

void loop() {
  if (Serial.available() && Serial.read() == 'r') run();
}
