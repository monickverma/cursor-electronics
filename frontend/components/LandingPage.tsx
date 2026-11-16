'use client'

/**
 * The front page, in the same world as the app: the live water, windows you can
 * drag, and a real design to poke at before signing in.
 *
 * The schematic on this page is the app's own SchematicDrawing, fed the recorded
 * output for one prompt (lib/landingExample.ts). Nothing on it is drawn for show.
 */

import { useEffect, useState } from 'react'
import FlowBackground from '@/components/FlowBackground'
import FloatWindow from '@/components/FloatWindow'
import SchematicDrawing from '@/components/SchematicDrawing'
import { LANDING_IR, LANDING_PROMPT } from '@/lib/landingExample'
import { prefersCalm } from '@/lib/flow'

interface Props {
  /** Open the app. A prompt, when given, is placed in the prompt bar ready to send. */
  onGetStarted: (prompt?: string) => void
}

const DEMO_URL =
  'https://drive.google.com/drive/folders/1GkFsTZ7xmXJsFuvLrNU-J_l4yDbeylfo?usp=sharing'
const REPO_URL = 'https://github.com/monickverma/cursor-electronics'
const DOCS_URL = `${REPO_URL}#readme`

// Each prompt states every value its generator needs, so it builds as written.
const TEMPLATES = [
  {
    label: 'Room monitor',
    desc: 'Several blocks on one board: a DHT22, a buzzer through a transistor switch, a status LED.',
    outputs: ['Board', 'Schematic', 'Firmware', 'Simulation', 'BOM'],
    prompt: 'Room monitor: an Uno reads a DHT22 on a 2 m cable, sounds a 30 mA buzzer above 30 °C, and lights a status LED at 10 mA',
  },
  {
    label: 'RS-485 Modbus',
    desc: 'MAX485 transceiver as a Modbus RTU master, with bias and termination resistors.',
    outputs: ['Board', 'Schematic', 'Firmware', 'Simulation', 'BOM'],
    prompt: 'Arduino Uno + MAX485 RS-485 Modbus RTU master at 9600 baud on a 5 V supply',
  },
  {
    label: 'LED indicator',
    desc: 'A current-limiting resistor sized for a GPIO-driven LED, proved over part tolerances.',
    outputs: ['Board', 'Schematic', 'Firmware', 'Simulation', 'BOM'],
    prompt: 'Arduino Uno driving a status LED at 10 mA from a 5 V supply',
  },
  {
    label: 'RC low-pass filter',
    desc: 'R and C picked from standard values for the cutoff you ask for; ngspice checks the −3 dB point.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    prompt: 'RC low-pass filter with a 1 kHz cutoff on a 5 V supply',
  },
  {
    label: 'Voltage divider',
    desc: 'Two standard resistors for the ratio you ask for; the DC operating point is simulated.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    prompt: 'Voltage divider stepping 5 V down to 3.3 V',
  },
]

const FEATURES = [
  {
    title: 'Physics simulation',
    desc: 'ngspice AC/DC analysis runs on every design. A 15% tolerance gate stops a bad design before you order parts.',
  },
  {
    title: 'The board in 3D',
    desc: 'Parts placed on a board you can orbit, with design-rule checks listed beside it. Experimental: routing is not finished, and it says so.',
  },
  {
    title: 'KiCad schematic',
    desc: 'A drawing you can trace net by net, and the net-label .kicad_sch file that opens in KiCad.',
  },
  {
    title: 'Firmware that compiled',
    desc: 'Deterministic templates, built with PlatformIO. Firmware is shown only once it compiles.',
  },
  {
    title: 'Component BOM',
    desc: 'Every row matches the design. Prices are dated catalogue prices, or a live Mouser quote when configured — a price never gates a validation.',
  },
  {
    title: 'Patch and edit',
    desc: 'Change a value in plain English. The requirement is edited and the design re-derived through the same checks; a change that cannot be justified is refused and the previous version is kept.',
  },
]

const PIPELINE = [
  'Parsing intent via tool_use',
  'Requirement → IntentIR',
  'Structural validation',
  'SPICE netlist compiler',
  'Arduino firmware (Jinja2)',
  'KiCad schematic (net labels)',
  'BOM compiler',
  'Simulation queued → Celery',
]

/** The pipeline's steps, ticking through once and resting on the queued simulation. */
function Pipeline() {
  const [done, setDone] = useState(PIPELINE.length)
  useEffect(() => {
    if (prefersCalm()) return
    setDone(0)
    const timer = setInterval(() => {
      setDone(n => {
        if (n >= PIPELINE.length) { clearInterval(timer); return n }
        return n + 1
      })
    }, 520)
    return () => clearInterval(timer)
  }, [])
  return (
    <div className="p-4 font-mono text-[13px] leading-7">
      <p className="text-muted">$ describe &quot;{LANDING_PROMPT}&quot;</p>
      <ol>
        {PIPELINE.map((step, i) => {
          const last = i === PIPELINE.length - 1
          const reached = i < done
          return (
            <li key={step} className={reached ? 'text-cream' : 'text-muted/50'}>
              <span aria-hidden="true" className="inline-block w-6">{!reached ? '·' : last ? '⟳' : '✓'}</span>
              {i + 1}. {step}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default function LandingPage({ onGetStarted }: Props) {
  return (
    <div className="flow-app">
      <FlowBackground />

      <div className="relative z-10">
        <header className="flex flex-wrap items-stretch justify-between gap-2">
          <span className="flex items-center min-h-[44px] px-3.5 bg-paper text-ink font-pixel text-2xl tracking-wider">
            CIRCUIT OS
          </span>
          <nav aria-label="Primary" className="flex flex-wrap items-stretch gap-1">
            <a href="#try" className="flex items-center min-h-[44px] px-3 text-sm underline underline-offset-4 hover:bg-paper hover:text-ink">try it</a>
            <a href="#included" className="flex items-center min-h-[44px] px-3 text-sm underline underline-offset-4 hover:bg-paper hover:text-ink">included</a>
            <a href="#templates" className="flex items-center min-h-[44px] px-3 text-sm underline underline-offset-4 hover:bg-paper hover:text-ink">templates</a>
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="flex items-center min-h-[44px] px-3 text-sm underline underline-offset-4 hover:bg-paper hover:text-ink">docs</a>
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="flex items-center min-h-[44px] px-3 text-sm underline underline-offset-4 hover:bg-paper hover:text-ink">github</a>
            <button type="button" className="flow-btn" onClick={() => onGetStarted()}>Open app</button>
          </nav>
        </header>

        {/* ── Hero ─────────────────────────────────────────────── */}
        <section className="flex flex-col items-center gap-6 px-6 pt-16 pb-14 text-center">
          <p className="text-sm">AI hardware compiler ...... Phase 1 · v0.1.0-rc</p>
          <h1 className="flow-headline max-w-[1200px]" style={{ fontSize: 'clamp(46px, 9.4vw, 136px)' }}>
            Don&apos;t Draw; Just Describe.
          </h1>
          <p className="max-w-[58ch] font-sans text-lg leading-relaxed">
            Plain English in. A schematic, a board, firmware, a simulation and a BOM out, with a reason
            given for every part and a plain statement of what was not checked.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <button type="button" className="flow-btn !min-h-[52px] !px-7 !text-lg" onClick={() => onGetStarted()}>
              Start a design →
            </button>
            <a href={DEMO_URL} target="_blank" rel="noopener noreferrer"
               className="flow-btn !min-h-[52px] !px-7 !text-lg inline-flex items-center !bg-transparent !text-paper !border-paper hover:!bg-paper hover:!text-ink">
              Watch the demo
            </a>
          </div>
          <p className="text-xs">Move the pointer: the water follows. Every window on this page can be dragged.</p>
        </section>

        {/* ── A real design to try ─────────────────────────────── */}
        <section id="try" className="px-6 pb-20 scroll-mt-6">
          <div className="mx-auto max-w-[1280px] flex flex-wrap items-start gap-7">
            <div className="flex-[4_1_340px] min-w-0 flex flex-col gap-7">
              <FloatWindow id="landing-pipeline" title="compile" meta="1 model call">
                <Pipeline />
              </FloatWindow>
              <FloatWindow id="landing-rule" title="The one rule">
                <div className="p-4 flex flex-col gap-2">
                  <p className="font-sans text-xl font-semibold leading-snug">
                    The model writes the requirement. It never writes the circuit.
                  </p>
                  <p className="text-sm leading-relaxed text-cream-dim">
                    Fixed generators turn the requirement into the design, and fixed compilers turn the
                    design into SPICE, KiCad and firmware. The same request gives the same board, every time.
                  </p>
                </div>
              </FloatWindow>
            </div>
            <div className="flex-[7_1_520px] min-w-0">
              <FloatWindow id="landing-schematic" title="Schematic" meta="try it: point at a net, click a part" height={520}>
                <SchematicDrawing ir={LANDING_IR} />
              </FloatWindow>
              <p className="mt-4 text-xs text-center">
                The recorded output for &ldquo;{LANDING_PROMPT}&rdquo;. Click R1 to read why it is 280 Ω.
              </p>
            </div>
          </div>
        </section>

        {/* ── What comes out ───────────────────────────────────── */}
        <section id="included" className="px-6 pb-20 scroll-mt-6">
          <div className="mx-auto max-w-[1280px] flex flex-col gap-8">
            <h2 className="flow-headline text-center" style={{ fontSize: 'clamp(34px, 5vw, 68px)' }}>
              One Sentence In; Six Things Out
            </h2>
            <div className="grid gap-7" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))' }}>
              {FEATURES.map((f, i) => (
                <FloatWindow key={f.title} id={`landing-feature-${i}`} title={f.title}>
                  <p className="p-4 text-sm leading-relaxed text-cream-dim">{f.desc}</p>
                </FloatWindow>
              ))}
            </div>
          </div>
        </section>

        {/* ── Why, and what was not checked ────────────────────── */}
        <section id="explanation" className="px-6 pb-20 scroll-mt-6">
          <div className="mx-auto max-w-[1080px] flex flex-col items-center gap-6 text-center">
            <p className="text-sm">The explanation is the product</p>
            <blockquote className="flow-headline" style={{ fontSize: 'clamp(26px, 3.6vw, 48px)', lineHeight: 1.08 }}>
              &ldquo;280Ω, the E96 value nearest 10 mA. Halving it would roughly double the current and,
              past 20 mA, overload the pin.&rdquo;
            </blockquote>
            <p className="max-w-[60ch] font-sans text-base leading-relaxed">
              That is the generator&apos;s own note on R1 above. Every part carries one, every claim carries a
              grade, and a rule that was not checked is printed as not assessed, never counted as passed.
            </p>
          </div>
        </section>

        {/* ── Templates ────────────────────────────────────────── */}
        <section id="templates" className="px-6 pb-24 scroll-mt-6">
          <div className="mx-auto max-w-[1080px] flex flex-col gap-6">
            <h2 className="flow-headline text-center" style={{ fontSize: 'clamp(34px, 5vw, 68px)' }}>
              Five Circuits It Builds Today
            </h2>
            <div className="paper border-[1.5px] border-ink shadow-[5px_5px_0_rgba(254,254,254,0.3)]">
              {TEMPLATES.map((t, i) => (
                <div key={t.label}
                     className={`flex flex-wrap items-center gap-x-6 gap-y-3 p-4 ${i ? 'border-t-[1.5px] border-ink' : ''}`}>
                  <div className="flex-[999_1_320px] min-w-0 flex flex-col gap-1">
                    <h3 className="text-lg">{t.label}</h3>
                    <p className="text-sm leading-relaxed text-cream-dim">{t.desc}</p>
                    <p className="font-mono text-xs text-muted">{t.outputs.join(' · ')}</p>
                  </div>
                  <button type="button" onClick={() => onGetStarted(t.prompt)}
                          aria-label={`Build the ${t.label}`}
                          className="flex-[1_1_auto] min-h-[44px] px-4 bg-ink text-paper border-[1.5px] border-ink font-sans text-[15px] font-semibold hover:bg-paper hover:text-ink">
                    Build this →
                  </button>
                </div>
              ))}
            </div>
            <p className="text-xs text-center">
              Each opens the app with its request already written out, values and all. Free-form circuits are not in yet.
            </p>
          </div>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-3 px-6 py-5 border-t border-paper/30 text-xs">
          <span className="font-pixel text-xl">CIRCUIT OS</span>
          <span>Phase 1 · v0.1.0-rc · AGPL-3.0</span>
          <span className="flex flex-wrap gap-4">
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4 !text-paper">docs</a>
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4 !text-paper">github</a>
            <a href={DEMO_URL} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4 !text-paper">demo video</a>
          </span>
        </footer>
      </div>
    </div>
  )
}
