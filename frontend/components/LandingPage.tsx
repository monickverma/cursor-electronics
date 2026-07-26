'use client'

import { useState, useEffect } from 'react'

interface Props {
  onGetStarted: () => void
}

const TEMPLATES = [
  {
    label: 'DHT22 Sensor',
    icon: '🌡',
    desc: 'Temperature & humidity monitoring with relay alert above configurable threshold.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    simLines: ['VCC    5.0000V  ✓', 'GND    0.0000V  ✓', 'DATA   3.3000V  ✓'],
    grade: 'DC operating point — PASS',
  },
  {
    label: 'RS-485 Modbus',
    icon: '📡',
    desc: 'MAX485 transceiver, Modbus RTU master, 9600 baud. Bias + termination resistors included.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    simLines: ['RS485_A  2.5000V  ✓', 'RS485_B  2.5000V  ✓', 'DE_RE    5.0000V  ✓'],
    grade: 'RS-485 termination — PASS',
  },
  {
    label: 'LED Control',
    icon: '💡',
    desc: 'Current-limiting resistor for GPIO-driven LED. Arduino Uno PWM or digital output.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    simLines: ['LED_A   4.3500V  ✓', 'LED_K   0.0000V  ✓', 'I_LED   18.2mA  ✓'],
    grade: 'DC operating point — PASS',
  },
  {
    label: 'RC Filter',
    icon: '〰',
    desc: '1590Ω + 100nF → 1kHz low-pass cutoff. ngspice AC sweep validates -3dB point.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    simLines: ['f=1001Hz  Vout=0.707V  ✓', 'f=500Hz   Vout=0.894V  ✓', 'f=2kHz    Vout=0.447V  ✓'],
    grade: 'AC sweep -3dB @ 1001 Hz — PASS',
  },
  {
    label: 'Voltage Divider',
    icon: '⚡',
    desc: '12V → 5V output. DC operating point analysis confirms node voltages within 15%.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    simLines: ['VIN   12.0000V  ✓', 'VOUT   5.0400V  ✓', 'GND    0.0000V  ✓'],
    grade: 'DC operating point — PASS',
  },
]

const FEATURES = [
  {
    icon: '〰',
    title: 'Physics Simulation',
    desc: 'ngspice AC/DC analysis runs on every design. 15% tolerance gate stops bad designs before you order parts.',
  },
  {
    icon: '📐',
    title: 'KiCad Schematic',
    desc: 'Net-label .kicad_sch output you can open immediately in KiCad. No manual net assignment.',
  },
  {
    icon: '⚙',
    title: 'Arduino Firmware',
    desc: 'Jinja2 templates produce deterministic .ino files. arduino-cli compiles and validates before you flash.',
  },
  {
    icon: '📋',
    title: 'Component BOM',
    desc: 'LCSC part numbers, static pricing, CSV export. Every row matches the design — no guessing what to order.',
  },
  {
    icon: '💬',
    title: 'AI Explanation',
    desc: 'Every component explained with failure consequences. "If you change R1 from 10k to 4.7k, here is what breaks."',
  },
  {
    icon: '✏',
    title: 'Patch & Edit',
    desc: 'Follow-up messages apply surgical patches — never regenerates from scratch. Full version history persisted.',
  },
]

const TESTIMONIALS = [
  {
    quote: 'I described an RS-485 Modbus master in plain English and got a wired schematic, firmware, and simulation result in 12 seconds. That used to take me two hours.',
    name: 'Hardware Engineer',
    role: 'Industrial IoT startup',
    initial: 'H',
  },
  {
    quote: 'The explanation told me exactly what would fail if I changed R1 from 10k to 4.7k. No other tool does this. This is what makes engineers actually trust AI output.',
    name: 'EE Graduate Student',
    role: 'University research lab',
    initial: 'E',
  },
  {
    quote: 'Used it to verify a DHT22 pull-up value before ordering parts. ngspice confirmed. Bench confirmed within 2%. Saved a full board spin.',
    name: 'Freelance Engineer',
    role: 'Hardware prototyping',
    initial: 'F',
  },
]

const STATS = [
  { value: '5', label: 'Circuit templates' },
  { value: '15s', label: 'Generation time' },
  { value: '177', label: 'Tests passing' },
  { value: '15%', label: 'Simulation tolerance' },
]

export default function LandingPage({ onGetStarted }: Props) {
  const [activeTemplate, setActiveTemplate] = useState(0)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  const tpl = TEMPLATES[activeTemplate]

  return (
    <div style={{ fontFamily: 'var(--font-body)', background: 'var(--lumen)', color: 'var(--vast)', overflowX: 'hidden' }}>

      {/* ─── NAV ─────────────────────────────────────────────── */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 60,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 2.5rem',
        background: scrolled ? 'rgba(255,255,235,0.88)' : 'var(--lumen)',
        backdropFilter: scrolled ? 'blur(14px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(14px)' : 'none',
        borderBottom: `1px solid ${scrolled ? 'rgba(26,26,26,0.10)' : 'transparent'}`,
        transition: 'all 0.25s',
      }}>
        <span style={{
          fontFamily: 'var(--font-heading)', fontStyle: 'italic',
          fontSize: '1.25rem', fontWeight: 500, letterSpacing: '-0.01em',
          color: 'var(--vast)',
        }}>
          Circuit OS
        </span>

        <div style={{ display: 'flex', gap: '2rem' }}>
          {['Templates', 'Simulation', 'Docs', 'GitHub'].map(l => (
            <a key={l} href="#"
              style={{ fontSize: '0.875rem', color: 'var(--text-muted-light)', textDecoration: 'none', transition: 'color 0.15s' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--vast)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted-light)')}>
              {l}
            </a>
          ))}
        </div>

        <button onClick={onGetStarted} className="btn-amber" style={{ padding: '8px 22px', fontSize: '0.875rem' }}>
          Get started free
        </button>
      </nav>

      {/* ─── HERO ────────────────────────────────────────────── */}
      <section style={{ padding: '7rem 2rem 0', maxWidth: 1200, margin: '0 auto', textAlign: 'center' }}>

        {/* Phase badge */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: 'var(--fathom)', color: 'var(--lumen)',
          fontSize: '0.8125rem', letterSpacing: '0.04em', fontWeight: 500,
          padding: '6px 18px', borderRadius: 100, marginBottom: '2.25rem',
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--glow)', display: 'inline-block' }} />
          Phase 1 — 10 / 12 launch criteria met
        </div>

        <h1 style={{
          fontFamily: 'var(--font-heading)',
          fontSize: 'clamp(4.5rem, 9vw, 7.5rem)',
          fontWeight: 500, lineHeight: 1.04,
          letterSpacing: '-0.035em',
          marginBottom: '1.5rem',
          color: 'var(--vast)',
        }}>
          Don&apos;t draw,<br />
          <em>just describe.</em>
        </h1>

        <p style={{
          fontSize: 'clamp(1rem, 2vw, 1.25rem)',
          color: 'var(--text-muted-light)',
          maxWidth: 580, margin: '0 auto 2.75rem',
          lineHeight: 1.7,
        }}>
          The AI hardware compiler that turns plain English into a physics-validated
          schematic, Arduino firmware, SPICE simulation, and BOM — in under 15 seconds.
        </p>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: '4.5rem', flexWrap: 'wrap' }}>
          <button onClick={onGetStarted} className="btn-amber" style={{ padding: '14px 34px', fontSize: '1rem', fontWeight: 600 }}>
            Generate your first circuit →
          </button>
          <button className="btn-ghost-light" style={{ padding: '14px 26px', fontSize: '1rem' }}>
            Read the docs
          </button>
        </div>

        {/* App preview card — dark, rounded top, bleeds to bottom of viewport like Flow */}
        <div style={{
          background: 'var(--vast)',
          borderRadius: '2.5rem 2.5rem 0 0',
          padding: '1.5rem 1.5rem 0',
          minHeight: 500,
          display: 'flex',
          gap: 2,
          overflow: 'hidden',
        }}>
          {/* Chat panel */}
          <div style={{
            width: 300, minWidth: 260, flexShrink: 0,
            background: '#111',
            borderRadius: '1.5rem 0 0 0',
            padding: '1.25rem',
            display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            <div style={{
              fontFamily: 'var(--font-heading)', fontStyle: 'italic',
              fontSize: '1rem', color: 'rgba(255,255,235,0.45)',
              borderBottom: '1px solid rgba(255,255,235,0.07)',
              paddingBottom: 12, marginBottom: 4,
            }}>Circuit OS</div>

            <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,235,0.3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Try an example
            </div>

            {[
              'Temperature sensor with DHT22, alert relay above 40°C',
              'Arduino + MAX485 RS-485 Modbus RTU master',
              'LED blink with current-limiting resistor',
            ].map((ex, i) => (
              <div key={i} style={{
                fontSize: '0.75rem',
                color: 'rgba(255,255,235,0.5)',
                background: 'rgba(255,255,235,0.04)',
                border: '1px solid rgba(255,255,235,0.07)',
                borderRadius: '0.625rem',
                padding: '8px 10px',
                lineHeight: 1.5,
              }}>{ex}</div>
            ))}

            <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { role: 'user', text: 'Arduino reads DHT22 and alerts above 30°C' },
                { role: 'ai', text: 'Generated 4-component DHT22 circuit — validation passed, firmware compiled, simulation queued.' },
              ].map((m, i) => (
                <div key={i} style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '88%',
                  background: m.role === 'user' ? 'var(--glow)' : 'rgba(255,255,255,0.06)',
                  color: m.role === 'user' ? '#1a1a1a' : 'rgba(255,255,235,0.85)',
                  borderRadius: m.role === 'user' ? '1rem 1rem 4px 1rem' : '1rem 1rem 1rem 4px',
                  padding: '8px 11px',
                  fontSize: '0.75rem',
                  lineHeight: 1.55,
                }}>{m.text}</div>
              ))}
            </div>
          </div>

          {/* Output panel */}
          <div style={{
            flex: 1,
            background: '#0d0d0d',
            borderRadius: '0 1.5rem 0 0',
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
          }}>
            {/* Tab bar */}
            <div style={{
              display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.06)',
              padding: '0 1.25rem',
            }}>
              {['Schematic', 'Firmware', 'Simulation', 'BOM', 'Validation'].map((t, i) => (
                <div key={t} style={{
                  padding: '10px 14px',
                  fontSize: '0.8125rem',
                  color: i === 0 ? 'var(--lumen)' : 'rgba(255,255,235,0.35)',
                  borderBottom: `2px solid ${i === 0 ? 'var(--glow)' : 'transparent'}`,
                  marginBottom: -1,
                  whiteSpace: 'nowrap',
                }}>{t}</div>
              ))}
            </div>

            {/* Schematic content */}
            <div style={{ flex: 1, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: 6, overflow: 'hidden' }}>
              <div style={{ color: 'rgba(255,255,235,0.3)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                ;; KiCad net-label schematic — Circuit OS v1
              </div>
              {[
                { c: '#f0d7ff', t: '(kicad_sch (version 20230121) (generator circuit_os)' },
                { c: 'rgba(255,169,70,0.7)', t: '  (label "VCC" (at 1000 1000 0) (effects (font (size 1.27 1.27))))' },
                { c: 'rgba(255,169,70,0.7)', t: '  (label "GND" (at 1600 1000 0) (effects (font (size 1.27 1.27))))' },
                { c: 'rgba(255,169,70,0.7)', t: '  (label "DHT22_DATA" (at 2200 1000 0))' },
                { c: 'rgba(255,255,235,0.25)', t: '  (global_label "VCC" (shape power_in) ...)' },
              ].map((l, i) => (
                <div key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: l.c, lineHeight: 1.6 }}>{l.t}</div>
              ))}

              <div style={{ marginTop: 'auto', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {['U1: ATmega328P', 'U2: DHT22', 'R1: 10kΩ pull-up', 'D1: LED', 'R2: 220Ω'].map(c => (
                  <span key={c} style={{
                    fontSize: '0.6875rem', padding: '3px 9px',
                    border: '1px solid rgba(240,215,255,0.25)',
                    borderRadius: 100, color: 'rgba(240,215,255,0.85)',
                    fontFamily: 'var(--font-mono)',
                  }}>{c}</span>
                ))}
              </div>

              <div style={{
                marginTop: 8,
                padding: '8px 14px',
                background: 'rgba(3,79,70,0.2)',
                border: '1px solid rgba(3,79,70,0.5)',
                borderRadius: '0.625rem',
                fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--lumen)',
              }}>
                ✓ Validation passed · ✓ Firmware compiled · ⟳ Simulation queued
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── SOCIAL PROOF BAR ────────────────────────────────── */}
      <section style={{ background: 'var(--vast)', padding: '3.5rem 2rem' }}>
        <p style={{
          textAlign: 'center',
          color: 'rgba(255,255,235,0.3)',
          fontSize: '0.8125rem', letterSpacing: '0.08em', textTransform: 'uppercase',
          marginBottom: '1.75rem',
        }}>Works with your existing toolchain</p>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '3.5rem', flexWrap: 'wrap' }}>
          {['Arduino', 'KiCad', 'ngspice', 'PostgreSQL', 'Redis', 'OpenRouter'].map(brand => (
            <span key={brand} style={{
              fontFamily: 'var(--font-heading)', fontStyle: 'italic',
              fontSize: '1.375rem', color: 'rgba(255,255,235,0.22)',
              fontWeight: 500, letterSpacing: '-0.01em',
            }}>{brand}</span>
          ))}
        </div>
      </section>

      {/* ─── SPEED ───────────────────────────────────────────── */}
      <section style={{ padding: '9rem 2.5rem', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5rem', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 380px' }}>
            <p style={{
              fontSize: '0.8125rem', fontWeight: 600, letterSpacing: '0.05em',
              textTransform: 'uppercase', color: 'var(--fathom)', marginBottom: '1rem',
            }}>Speed</p>

            <h2 style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'clamp(2.5rem, 5vw, 4rem)',
              fontWeight: 500, lineHeight: 1.08, letterSpacing: '-0.025em',
              marginBottom: '1.75rem',
            }}>
              10× faster than<br /><em>manual design</em>
            </h2>

            <p style={{ fontSize: '1rem', color: 'var(--text-muted-light)', lineHeight: 1.75, marginBottom: '2.5rem', maxWidth: 400 }}>
              Manual schematic + firmware + simulation takes an experienced engineer 4–8 hours.
              Circuit OS does the same in 15 seconds — with physics-validated results.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {[
                { label: 'Manual design', time: '4 – 8 hours', pct: 100, color: 'var(--lumen-dim)' },
                { label: 'Circuit OS', time: '~15 seconds', pct: 0.5, color: 'var(--glow)' },
              ].map(bar => (
                <div key={bar.label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9375rem', marginBottom: 9, color: 'var(--vast)' }}>
                    <span style={{ fontWeight: 500 }}>{bar.label}</span>
                    <span style={{ color: 'var(--text-muted-light)' }}>{bar.time}</span>
                  </div>
                  <div style={{ height: 14, background: 'rgba(26,26,26,0.08)', borderRadius: 100, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${bar.pct}%`, background: bar.color, borderRadius: 100 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Terminal preview */}
          <div style={{
            flex: '1 1 360px',
            background: 'var(--vast)', borderRadius: '2rem', padding: '2rem',
            minHeight: 300,
          }}>
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'rgba(255,255,235,0.35)', marginBottom: 16 }}>
              $ describe "DHT22 alert above 30°C"
            </div>
            {[
              { step: '1. Parsing intent via tool_use', done: true },
              { step: '2. CircuitIR schema generation', done: true },
              { step: '3. Structural validation', done: true },
              { step: '4. SPICE netlist compiler', done: true },
              { step: '5. Arduino firmware (Jinja2)', done: true },
              { step: '6. KiCad schematic (net labels)', done: true },
              { step: '7. BOM compiler (static pricing)', done: true },
              { step: '8. Simulation queued → Celery', done: false, active: true },
            ].map(s => (
              <div key={s.step} style={{ display: 'flex', gap: 10, padding: '5px 0', fontSize: '0.8125rem', fontFamily: 'var(--font-mono)' }}>
                <span style={{ color: s.done ? 'var(--glow)' : s.active ? '#f0d7ff' : 'rgba(255,255,235,0.15)', flexShrink: 0 }}>
                  {s.done ? '✓' : s.active ? '⟳' : '○'}
                </span>
                <span style={{ color: s.done ? 'rgba(255,255,235,0.65)' : s.active ? '#f0d7ff' : 'rgba(255,255,235,0.2)' }}>
                  {s.step}
                </span>
              </div>
            ))}
            <div style={{
              marginTop: 16, padding: '10px 14px',
              background: 'rgba(3,79,70,0.2)', border: '1px solid rgba(3,79,70,0.5)',
              borderRadius: '0.75rem',
              fontSize: '0.8125rem', fontFamily: 'var(--font-mono)', color: 'var(--lumen)',
            }}>
              ✓ Complete — 14.3s · Validation passed · Firmware compiled
            </div>
          </div>
        </div>
      </section>

      {/* ─── TEMPLATES ───────────────────────────────────────── */}
      <section style={{
        background: 'var(--vast)',
        borderRadius: '5rem 5rem 0 0',
        padding: '8rem 2.5rem',
        marginTop: '2rem',
      }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <p style={{
            textAlign: 'center', fontSize: '0.8125rem', fontWeight: 600,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            color: 'var(--glow)', marginBottom: '1rem',
          }}>Phase 1 — 5 templates</p>

          <h2 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(2.5rem, 5vw, 4rem)',
            fontWeight: 500, lineHeight: 1.08, letterSpacing: '-0.025em',
            color: 'var(--lumen)', textAlign: 'center',
            marginBottom: '1.25rem',
          }}>
            Made for the circuits<br /><em>you build</em>
          </h2>

          <p style={{ textAlign: 'center', color: 'rgba(255,255,235,0.5)', fontSize: '1rem', lineHeight: 1.7, maxWidth: 500, margin: '0 auto 3.5rem' }}>
            Five templates that work 100% of the time — validated end-to-end before the next was added.
          </p>

          {/* Pills */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap', marginBottom: '3rem' }}>
            {TEMPLATES.map((t, i) => (
              <button key={t.label} onClick={() => setActiveTemplate(i)} style={{
                padding: '10px 20px', borderRadius: 100,
                border: `1.5px solid ${i === activeTemplate ? 'var(--glow)' : 'rgba(255,255,235,0.15)'}`,
                background: i === activeTemplate ? 'var(--glow)' : 'transparent',
                color: i === activeTemplate ? 'var(--vast)' : 'rgba(255,255,235,0.6)',
                fontSize: '0.875rem', fontWeight: i === activeTemplate ? 600 : 400,
                cursor: 'pointer', transition: 'all 0.15s',
              }}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          {/* Template preview */}
          <div style={{
            background: '#111', borderRadius: '2rem',
            padding: '2rem', display: 'grid',
            gridTemplateColumns: '1fr 1fr', gap: '2rem',
          }}>
            <div>
              <h3 style={{
                fontFamily: 'var(--font-heading)', fontStyle: 'italic',
                fontSize: '1.625rem', color: 'var(--lumen)', marginBottom: '0.75rem',
              }}>{tpl.label}</h3>
              <p style={{ color: 'rgba(255,255,235,0.55)', fontSize: '0.9375rem', lineHeight: 1.7, marginBottom: '1.5rem' }}>
                {tpl.desc}
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {tpl.outputs.map(tag => (
                  <span key={tag} style={{
                    fontSize: '0.75rem', padding: '4px 11px',
                    border: '1px solid rgba(240,215,255,0.3)',
                    borderRadius: 100, color: '#f0d7ff',
                    fontFamily: 'var(--font-mono)',
                  }}>{tag}</span>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'rgba(255,169,70,0.6)' }}>
                ngspice simulation output
              </div>
              <div style={{ flex: 1, background: '#0a0a0a', borderRadius: '1rem', padding: '1rem', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {tpl.simLines.map(line => (
                  <div key={line} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'rgba(255,255,235,0.6)' }}>{line}</div>
                ))}
                <div style={{ color: 'var(--glow)', fontSize: '0.8125rem', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                  ✓ Grade: {tpl.grade}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── FEATURES GRID ───────────────────────────────────── */}
      <section style={{ padding: '9rem 2.5rem', maxWidth: 1100, margin: '0 auto' }}>
        <p style={{
          textAlign: 'center', fontSize: '0.8125rem', fontWeight: 600,
          letterSpacing: '0.05em', textTransform: 'uppercase',
          color: 'var(--fathom)', marginBottom: '1rem',
        }}>Everything included</p>

        <h2 style={{
          fontFamily: 'var(--font-heading)',
          fontSize: 'clamp(2.5rem, 5vw, 4rem)',
          fontWeight: 500, lineHeight: 1.08, letterSpacing: '-0.025em',
          textAlign: 'center', marginBottom: '1rem',
        }}>
          One prompt.<br /><em>Your complete design.</em>
        </h2>

        <p style={{ textAlign: 'center', color: 'var(--text-muted-light)', marginBottom: '4rem', fontSize: '1rem', lineHeight: 1.7 }}>
          No separate tools. No manual steps. One workflow.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: '1.25rem' }}>
          {FEATURES.map(f => (
            <div key={f.title}
              style={{
                background: '#fff', border: '1px solid rgba(26,26,26,0.10)',
                borderRadius: '1.5rem', padding: '2rem',
                transition: 'transform 0.18s, box-shadow 0.18s',
                cursor: 'default',
              }}
              onMouseEnter={e => {
                const el = e.currentTarget as HTMLElement
                el.style.transform = 'translateY(-4px)'
                el.style.boxShadow = '0 16px 48px rgba(26,26,26,0.08)'
              }}
              onMouseLeave={e => {
                const el = e.currentTarget as HTMLElement
                el.style.transform = 'none'
                el.style.boxShadow = 'none'
              }}
            >
              <div style={{ fontSize: '1.75rem', marginBottom: '1rem' }}>{f.icon}</div>
              <h3 style={{
                fontFamily: 'var(--font-heading)', fontSize: '1.25rem',
                fontWeight: 500, marginBottom: '0.75rem', color: 'var(--vast)',
              }}>{f.title}</h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-muted-light)', lineHeight: 1.75 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── EXPLANATION DEEP-DIVE (teal) ────────────────────── */}
      <section style={{
        background: 'var(--fathom)',
        borderRadius: '5rem', margin: '0 1rem',
        padding: '8rem 2.5rem',
      }}>
        <div style={{ maxWidth: 860, margin: '0 auto', textAlign: 'center' }}>
          <h2 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(2.5rem, 5vw, 3.75rem)',
            fontWeight: 500, lineHeight: 1.08, letterSpacing: '-0.025em',
            color: 'var(--lumen)', marginBottom: '1.5rem',
          }}>
            The explanation layer<br /><em>is the product.</em>
          </h2>

          <p style={{ fontSize: '1.125rem', color: 'rgba(255,255,235,0.65)', lineHeight: 1.75, maxWidth: 540, margin: '0 auto 3rem' }}>
            Any engineer can run ngspice. What no tool does is look at your circuit and tell you
            exactly what breaks — and why.
          </p>

          <div style={{
            background: 'rgba(2,46,40,0.7)', borderRadius: '1.5rem', padding: '2rem',
            textAlign: 'left', fontFamily: 'var(--font-mono)', fontSize: '0.875rem', lineHeight: 1.85,
            border: '1px solid rgba(255,255,235,0.08)',
          }}>
            <div style={{ color: 'rgba(255,255,235,0.35)', marginBottom: 10 }}>// ExplanationEngine output — DHT22 circuit, component R1</div>
            <div style={{ color: 'var(--lumen)' }}>R1 (10kΩ) pulls the DHT22 DATA line high between transmissions.</div>
            <div style={{ color: 'var(--glow)', marginTop: 10 }}>⚠ Without R1: the open-drain output never reaches logic HIGH.</div>
            <div style={{ color: 'var(--glow)' }}>⚠ Every read returns a timeout. The MCU loops indefinitely.</div>
            <div style={{ color: 'rgba(255,255,235,0.5)', marginTop: 10 }}>Lowering R1 below 3kΩ exceeds DHT22&apos;s 5mA maximum sink current at 5V.</div>
            <div style={{ color: 'rgba(255,255,235,0.5)' }}>Simulation at 1kΩ: 5mA → datasheet limit. At 10kΩ: 0.5mA → safe.</div>
          </div>
        </div>
      </section>

      {/* ─── TESTIMONIALS ────────────────────────────────────── */}
      <section style={{ background: 'var(--vast)', padding: '8rem 2.5rem' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <h2 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(2.5rem, 5vw, 4rem)',
            fontWeight: 500, lineHeight: 1.08, letterSpacing: '-0.025em',
            color: 'var(--lumen)', textAlign: 'center', marginBottom: '4rem',
          }}>
            Love letters<br /><em>from engineers</em>
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
            {TESTIMONIALS.map((t, i) => (
              <div key={i} style={{
                background: '#111', border: '1px solid rgba(255,255,235,0.07)',
                borderRadius: '1.5rem', padding: '2rem',
              }}>
                <p style={{ fontSize: '0.9375rem', color: 'rgba(255,255,235,0.75)', lineHeight: 1.75, marginBottom: '1.5rem', fontStyle: 'italic' }}>
                  &ldquo;{t.quote}&rdquo;
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: '50%',
                    background: 'var(--fathom)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.875rem', color: 'var(--lumen)', fontWeight: 600, flexShrink: 0,
                  }}>{t.initial}</div>
                  <div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--lumen)', fontWeight: 500 }}>{t.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,235,0.35)' }}>{t.role}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── STATS ───────────────────────────────────────────── */}
      <section style={{ padding: '6rem 2.5rem', maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.25rem' }}>
          {STATS.map(s => (
            <div key={s.label} style={{
              textAlign: 'center', padding: '2.5rem 1rem',
              background: '#fff', border: '1px solid rgba(26,26,26,0.10)',
              borderRadius: '1.5rem',
            }}>
              <div style={{
                fontFamily: 'var(--font-heading)',
                fontSize: 'clamp(2.5rem, 4vw, 3.5rem)',
                fontWeight: 500, color: 'var(--vast)', lineHeight: 1,
                marginBottom: '0.5rem',
              }}>{s.value}</div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-muted-light)' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── CTA ─────────────────────────────────────────────── */}
      <section style={{
        background: 'var(--vast)', margin: '0 1rem 1rem',
        borderRadius: '4rem', padding: '9rem 2rem',
        textAlign: 'center', position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(ellipse 55% 45% at 50% 65%, rgba(3,79,70,0.45) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{ position: 'relative' }}>
          <h2 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(3.25rem, 8vw, 6.5rem)',
            fontWeight: 500, lineHeight: 1.04, letterSpacing: '-0.035em',
            color: 'var(--lumen)', marginBottom: '1.5rem',
          }}>
            Start compiling…
          </h2>
          <p style={{ fontSize: '1.125rem', color: 'rgba(255,255,235,0.55)', maxWidth: 480, margin: '0 auto 3rem', lineHeight: 1.7 }}>
            Describe your circuit in plain English. Get a physics-validated design back in 15 seconds. No setup. No tools. No guessing.
          </p>
          <button onClick={onGetStarted} className="btn-amber" style={{ padding: '16px 44px', fontSize: '1.0625rem', fontWeight: 600 }}>
            Generate your first circuit →
          </button>
        </div>
      </section>

      {/* ─── FOOTER ──────────────────────────────────────────── */}
      <footer style={{ padding: '3rem 2.5rem 0' }}>
        {/* Top row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16, marginBottom: '3rem' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontStyle: 'italic', fontSize: '1.125rem', fontWeight: 500 }}>Circuit OS</span>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            {['Templates', 'Simulation', 'Firmware', 'BOM', 'Docs', 'GitHub'].map(l => (
              <a key={l} href="#" style={{ fontSize: '0.875rem', color: 'var(--text-muted-light)', textDecoration: 'none' }}>{l}</a>
            ))}
          </div>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted-light)' }}>Phase 1 · v0.1.0-rc · MIT</span>
        </div>

        {/* Large wordmark — matches Flow's "••••• Flow" footer treatment */}
        <div style={{
          borderTop: '1px solid rgba(26,26,26,0.10)',
          paddingTop: '2rem', paddingBottom: '2rem',
          textAlign: 'center',
        }}>
          <span style={{
            fontFamily: 'var(--font-heading)', fontStyle: 'italic',
            fontSize: 'clamp(4rem, 10vw, 8rem)',
            fontWeight: 500, letterSpacing: '-0.04em',
            color: 'rgba(26,26,26,0.08)',
            userSelect: 'none',
          }}>Circuit OS</span>
        </div>
      </footer>

    </div>
  )
}
