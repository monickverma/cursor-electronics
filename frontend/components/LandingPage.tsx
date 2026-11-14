'use client'

/**
 * Landing page — the cover sheet of the drawing set.
 *
 * Same type (Archivo with its width axis, JetBrains Mono) and the same tokens as the workbench
 * (globals.css: --bench-*, --paper*, --ink*, --fg*, --line*, verdict tokens). Colour appears only
 * where a verdict is stated. Structure and motion are the owner's chosen feel and are kept:
 * Lenis on the GSAP ticker, the hero scrubbed on exit, the footer rising, the centred nav that sticks
 * and blends with `difference` after the hero.
 *
 * Every figure on this page is a recorded value from frontend/lib/demo/examples.json (recorded
 * 2026-10-12 by scripts/build_demo_fixtures.py — the deterministic pipeline run locally). They were
 * read with a script, not typed from memory; if the recordings are rebuilt, re-read them.
 */
import { useEffect, useRef } from 'react'
import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Chip, GradeChip, VERDICTS } from '@/components/ui'
import styles from './LandingPage.module.css'

interface Props {
  onGetStarted: () => void
}

const DEMO_URL =
  'https://drive.google.com/drive/folders/1GkFsTZ7xmXJsFuvLrNU-J_l4yDbeylfo?usp=sharing'
const REPO_URL = 'https://github.com/monickverma/cursor-electronics'
const DOCS_URL = `${REPO_URL}#readme`

/* ── The recorded room-monitor example (examples.json → slug "room-monitor") ─────────────────── */
const ROOM = {
  recordedOn: '2026-10-12',
  intent: 'Room monitor: an Uno reads a DHT22, sounds a buzzer above 30 °C, and lights a status LED',
  applicationClass: 'hobby_arduino',
  targetMcu: 'arduino_uno',
  version: 1,
  generator: 'compose@0.1.0',
  circuitId: 'f42051c2-d905-55ee-b9b1-4b5f4fb25c3e',
  // validation_coverage.claims grouped by verdict (not_assessed 1 + out_of_scope 18 = 19)
  claims: { holds: 16, defeasible: 27, fails: 0, open: 19 },
  gradeFloor: 'G2',
  openDefeaters: ['D1', 'D2', 'D7'],
  properties: { proven: 10, total: 10, signed: false },
  rules: { errors: 0, warnings: 0 },
  simulation: { passed: true, durationMs: 463 },
  firmware: { status: 'compiled', board: 'Arduino Uno R3' },
  bomLines: 10,
  components: 10,
  nets: 8,
} as const

/* ── Hero readout: the room monitor's recorded run, stage by stage ───────────────────────────── */
const PIPELINE: { stage: string; result: string }[] = [
  { stage: 'requirement → IntentIR', result: '3 blocks' },
  { stage: 'generator', result: ROOM.generator },
  { stage: 'structural rules', result: '0 errors' },
  { stage: 'proofs over tolerances', result: `${ROOM.properties.proven} of ${ROOM.properties.total}` },
  { stage: 'ngspice operating point', result: 'passed' },
  { stage: 'PlatformIO build', result: 'compiled' },
  { stage: 'KiCad schematic', result: `${ROOM.nets} nets` },
  { stage: 'bill of materials', result: `${ROOM.bomLines} lines` },
]

/* ── Templates — each panel prints values recorded for that circuit ─────────────────────────── */
const TEMPLATES = [
  {
    label: 'DHT22 sensor',
    desc: 'Temperature and humidity on an Arduino, with the DATA pull-up sized for the cable. Figures from the room monitor, where it is one of three blocks on the board.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    lines: [['R1 pull-up', '10 kΩ'], ['DHT22_DATA', '4.99995 V'], ['VCC_5V', '5 V']],
    verdict: 'simulation passed · 463 ms',
    ratio: '5 / 4',
  },
  {
    label: 'RS-485 Modbus',
    desc: 'MAX485 transceiver as a Modbus RTU master at 9600 baud, with 120 Ω termination and fail-safe bias, wired as its firmware drives it.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    lines: [['RS485_A', '2.746305 V'], ['RS485_B', '2.253695 V'], ['R2, R3 bias', '549 Ω']],
    verdict: 'simulation passed · 498 ms',
    ratio: '4 / 3',
  },
  {
    label: 'LED indicator',
    desc: 'A GPIO-driven LED and its current-limiting resistor, sized to the requested current — 10 mA in the recorded example.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    lines: [['R1', '280 Ω'], ['LED_ANODE', '1.963908 V'], ['I pin', '9.9544 mA']],
    verdict: 'simulation passed · 453 ms',
    ratio: '1 / 1',
  },
  {
    label: 'RC low-pass',
    desc: 'A first-order low-pass at the requested cutoff — 1 kHz on a 5 V supply in the recorded example. An ngspice AC sweep finds the −3 dB point.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    lines: [['R1 · C1', '3.4 kΩ · 47 nF'], ['−3 dB at', '995.96 Hz'], ['OUT there', '3.535534 V']],
    verdict: 'simulation passed · 453 ms',
    ratio: '5 / 4',
  },
  {
    label: 'Voltage divider',
    desc: 'Two resistors to a requested output — 5 V down to 3.3 V in the recorded example — checked at the DC operating point.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    lines: [['R1 · R2', '3.4 kΩ · 6.65 kΩ'], ['VIN', '5 V'], ['VOUT', '3.308458 V']],
    verdict: 'simulation passed · 620 ms',
    ratio: '1 / 1',
  },
]

/* ── The drawing set — mirrors components/workbench/sheets.ts (the app's empty-state index) ─── */
const SHEETS = [
  {
    n: '00', name: 'Overview',
    about: 'The compile report: claims counted by verdict, the grade floor, each stage of the pipeline, and why each part was chosen.',
    trust: 'Built only from what the compiler returned. A value it did not produce is not drawn.',
  },
  {
    n: '01', name: 'Schematic',
    about: 'The KiCad schematic the compiler wrote from the IR, connected by net labels, with its source.',
    trust: 'Written by a deterministic compiler from the IR — never by the language model.',
  },
  {
    n: '02', name: 'PCB', experimental: true,
    about: 'An experimental placement and route in 2D and 3D, with the board verifier’s findings.',
    trust: 'Outside the release gate. No Gerber export, no fab ordering, no layout physics.',
  },
  {
    n: '03', name: 'Firmware',
    about: 'The sketch and PlatformIO project for the design’s board — shown only once it compiles.',
    trust: 'Rendered from templates and built under PlatformIO for the Uno, ESP32-DevKitC or Black Pill.',
  },
  {
    n: '04', name: 'Simulation',
    about: 'The ngspice run, graded against the requirement: operating point, sweeps and transients.',
    trust: 'A simulation, not a measurement. Nothing has been built or measured on a bench.',
  },
  {
    n: '05', name: 'BOM',
    about: 'Every part with a dated price and its source, totals per currency, and substitutes re-checked before they are offered.',
    trust: 'A price never gates validation. A substitute is re-derived and re-proved before it is offered.',
  },
  {
    n: '06', name: 'Validation',
    about: 'Rule results, every claim with its verdict and grade, and proved properties to sign.',
    trust: 'Properties are proved over component tolerances. A check that was not run is printed as not assessed.',
  },
]

const LEGEND = [
  { v: VERDICTS.holds, tone: 'pass', means: 'The check ran and the claim holds.' },
  { v: VERDICTS.holds_defeasible, tone: 'warn', means: 'It holds, with a named open doubt — a defeater — that could overturn it.' },
  { v: VERDICTS.fails, tone: 'fail', means: 'The check ran and the claim fails.' },
  { v: VERDICTS.not_assessed, tone: 'none', means: 'Not checked, and printed as such — never counted as a pass.' },
] as const

export default function LandingPage({ onGetStarted }: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  const navRef = useRef<HTMLElement>(null)
  const heroRef = useRef<HTMLElement>(null)
  const zoomRef = useRef<HTMLDivElement>(null)
  const mainRef = useRef<HTMLElement>(null)
  const footerRef = useRef<HTMLElement>(null)
  const tipRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const root = rootRef.current
    const nav = navRef.current
    const hero = heroRef.current
    const zoom = zoomRef.current
    const main = mainRef.current
    const footer = footerRef.current
    const tip = tipRef.current
    if (!root || !nav || !hero || !zoom || !main || !footer || !tip) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const html = document.documentElement
    const prev = {
      gutter: html.style.scrollbarGutter,
      overscroll: html.style.overscrollBehavior,
      bg: document.body.style.background,
      restoration: history.scrollRestoration,
    }
    html.style.scrollbarGutter = 'stable'
    html.style.overscrollBehavior = 'none'
    document.body.style.background = 'var(--bench-0)'
    history.scrollRestoration = 'manual'
    window.scrollTo(0, 0)

    gsap.registerPlugin(ScrollTrigger)

    // Smooth scroll with inertia: Lenis defaults (lerp 0.1), driven by the GSAP clock
    // so scroll and every scrubbed animation share one timer.
    let lenis: Lenis | null = null
    let raf: ((t: number) => void) | null = null
    if (!reduce) {
      lenis = new Lenis()
      raf = (t: number) => lenis!.raf(t * 1000)
      gsap.ticker.add(raf)
      gsap.ticker.lagSmoothing(0)
      lenis.on('scroll', ScrollTrigger.update)
    }

    // Menu: starts vertically centred and scrolls away with the page, then sticks to the top.
    // After the hero it blends with `difference` so it reads on both black and white.
    const placeNav = () => {
      const y = window.scrollY
      const wide = window.innerWidth >= 1024
      const off = wide ? Math.max(0, window.innerHeight / 2 - nav.offsetHeight / 2 - y) : 0
      nav.style.transform = `translate3d(0, ${off}px, 0)`
      nav.classList.toggle(styles.navBlend, y > window.innerHeight * 0.5)
    }
    placeNav()
    window.addEventListener('scroll', placeNav, { passive: true })
    window.addEventListener('resize', placeNav)

    // Cursor label over [data-tooltip] elements.
    let px = -100
    let py = -100
    const updateTip = () => {
      const hit = document.elementFromPoint(px, py)?.closest<HTMLElement>('[data-tooltip]')
      if (hit) {
        tip.textContent = hit.dataset.tooltip ?? ''
        tip.style.opacity = '1'
      } else {
        tip.style.opacity = '0'
      }
      tip.style.transform = `translate3d(${px + 16}px, ${py + 16}px, 0)`
    }
    const onMove = (e: PointerEvent) => {
      if (e.pointerType === 'touch') return
      px = e.clientX
      py = e.clientY
      updateTip()
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('scroll', updateTip, { passive: true })

    const ctx = gsap.context(() => {
      const reveals = gsap.utils.toArray<HTMLElement>('[data-reveal]', root)
      const rules = gsap.utils.toArray<HTMLElement>('[data-rule] > i', root)
      const zooms = gsap.utils.toArray<HTMLElement>('[data-zoom]', root)

      if (reduce) {
        gsap.set(reveals, { opacity: 1, y: 0 })
        gsap.set(rules, { xPercent: 0 })
        return
      }

      // Hero: grows and fades while it scrolls away; plays backward on the way up.
      gsap.set(zoom, { willChange: 'transform, opacity' })
      gsap.fromTo(
        zoom,
        { scale: 1, opacity: 1 },
        {
          scale: 2,
          opacity: 0,
          ease: 'none',
          immediateRender: false,
          scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true },
        },
      )

      // Footer: starts 80% of its height below and rises as the white page ends.
      gsap.fromTo(
        footer,
        { yPercent: 80 },
        {
          yPercent: 0,
          ease: 'none',
          scrollTrigger: {
            trigger: main,
            start: 'bottom bottom',
            end: () => `+=${footer.offsetHeight}`,
            scrub: true,
            invalidateOnRefresh: true,
          },
        },
      )

      // Entry reveal: 20px up, fade in.
      gsap.set(reveals, { y: 20 })
      ScrollTrigger.batch(reveals, {
        start: 'top 92%',
        once: true,
        onEnter: (els) =>
          gsap.to(els, { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out', stagger: 0.08, overwrite: true }),
      })

      // Panels settle from 1.2 → 1 once, as they enter.
      zooms.forEach((el) => {
        const inner = el.firstElementChild as HTMLElement | null
        if (!inner) return
        gsap.set(inner, { scale: 1.2 })
        ScrollTrigger.create({
          trigger: el,
          start: 'top 92%',
          once: true,
          onEnter: () => {
            inner.style.willChange = 'transform'
            gsap.to(inner, {
              scale: 1,
              duration: 2.5,
              ease: 'power2.out',
              onComplete: () => {
                inner.style.willChange = 'auto'
              },
            })
          },
        })
      })

      // Thin rules draw in from the left.
      rules.forEach((line) => {
        ScrollTrigger.create({
          trigger: line.parentElement,
          start: 'top 95%',
          once: true,
          onEnter: () => gsap.to(line, { xPercent: 101, duration: 1.2, ease: 'power4.inOut' }),
        })
      })
    }, root)

    ScrollTrigger.refresh()

    return () => {
      ctx.revert()
      window.removeEventListener('scroll', placeNav)
      window.removeEventListener('resize', placeNav)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('scroll', updateTip)
      if (raf) gsap.ticker.remove(raf)
      gsap.ticker.lagSmoothing(500, 33)
      lenis?.destroy()
      html.style.scrollbarGutter = prev.gutter
      html.style.overscrollBehavior = prev.overscroll
      document.body.style.background = prev.bg
      history.scrollRestoration = prev.restoration
    }
  }, [])

  return (
    <div ref={rootRef} className={styles.root}>
      {/* ── Nav ───────────────────────────────────────────── */}
      <nav ref={navRef} className={styles.nav} aria-label="Primary">
        <span className={styles.navBrand}>
          <span className="tb-mark" aria-hidden="true" />
          <span className="t-wordmark">Circuit OS</span>
        </span>
        <span className={styles.navGroup}>
          <a href="#sheets" className={styles.ulink}>Sheets</a>
          <a href="#example" className={styles.ulink}>Example</a>
          <a href="#templates" className={styles.ulink}>Templates</a>
          <a href={DOCS_URL} className={styles.ulink} target="_blank" rel="noopener noreferrer">Docs ↗</a>
          <a href={REPO_URL} className={styles.ulink} target="_blank" rel="noopener noreferrer">GitHub ↗</a>
        </span>
        <span className={styles.navTag}>AI hardware compiler</span>
        <span className={styles.navCta}>
          <button type="button" className={styles.navButton} onClick={onGetStarted}>
            Get started
          </button>
        </span>
      </nav>

      {/* ── Hero ──────────────────────────────────────────── */}
      <section ref={heroRef} className={styles.hero}>
        <div ref={zoomRef} className={styles.heroZoom}>
          <div className={styles.heroTop}>
          <div className={styles.heroMeta}>
            <span>Sheet 00 · Cover</span>
            <span>Plain English in. Schematic, firmware, simulation, BOM and graded claims out.</span>
          </div>
          <div className={styles.heroReadout} aria-hidden="true">
            <div className={styles.readHead}>
              <span>Recorded run</span>
              <span>room monitor · rev v{ROOM.version}</span>
            </div>
            {PIPELINE.map((p, i) => (
              <div key={p.stage} className={styles.readRow}>
                <span className={styles.readNum}>{String(i + 1).padStart(2, '0')}</span>
                <span className={styles.readStage}>{p.stage}</span>
                <span className={styles.readResult}>{p.result}</span>
                <span className={styles.readOk}>✓</span>
              </div>
            ))}
          </div>
          </div>

          <div className={styles.heroBottom}>
            <h1 className={styles.heroTitle}>
              <span className={styles.heroLine}>Don’t draw,</span>
              <span className={styles.heroLine}>just describe.</span>
            </h1>
          </div>
        </div>
      </section>

      {/* ── Main (paper) ─────────────────────────────────── */}
      <main ref={mainRef} className={styles.main}>
        <section className={styles.statement}>
          <span className={`${styles.label} ${styles.reveal}`} data-reveal>
            AI hardware compiler
          </span>
          <p className={`${styles.statementText} ${styles.big} ${styles.reveal}`} data-reveal>
            Circuit OS turns a plain-English description into a drawing set — a schematic, firmware
            that compiles, an ngspice simulation, a bill of materials and a graded claim for every
            check — for an Arduino Uno, an ESP32-DevKitC or an STM32 Black Pill.
          </p>
        </section>

        <section className={styles.vision}>
          <span className={styles.rule} data-rule><i /></span>
          <span className={`${styles.visionLabel} ${styles.label} ${styles.reveal}`} data-reveal>
            Principle
          </span>
          <div className={styles.visionBody}>
            <p className={`${styles.normal} ${styles.reveal}`} data-reveal>
              The language model never writes SPICE, KiCad files or firmware. It writes a structured
              description of the requirement, and deterministic compilers turn that into every
              sheet. The same requirement gives the same design, and a request that cannot be
              justified is refused instead of negotiated. A change in plain English edits the
              requirement, and the design is derived again through the same checks.
            </p>
            <p className={`${styles.normal} ${styles.reveal}`} data-reveal>
              Today it knows five circuits — a DHT22 sensor, an RS-485 Modbus node, an LED, an RC
              low-pass and a voltage divider — and composes several of them on one board.
            </p>
            <div className={`${styles.rows} ${styles.normal}`}>
              <div className={styles.row}>
                <span className={styles.rule} data-rule><i /></span>
                <button type="button" className={styles.cta} onClick={onGetStarted}>
                  <span>Open app</span>
                  <span aria-hidden="true">→</span>
                  <span className={styles.ctaLines}><i className={styles.ctaLine1} /><i className={styles.ctaLine2} /></span>
                </button>
              </div>
              <div className={styles.row}>
                <a className={styles.cta} href={DEMO_URL} target="_blank" rel="noopener noreferrer">
                  <span>Demo video</span>
                  <span aria-hidden="true">↗</span>
                  <span className={styles.ctaLines}><i className={styles.ctaLine1} /><i className={styles.ctaLine2} /></span>
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ── The drawing set ─────────────────────────────── */}
        <section id="sheets" className={styles.sheets}>
          <div className={styles.sectionHead}>
            <h2 className={styles.h2}>The drawing set</h2>
            <span className={styles.headNote}>Seven sheets, one per output</span>
          </div>
          <ol className={styles.list}>
            {SHEETS.map((s) => (
              <li key={s.n} className={`${styles.li} ${styles.reveal}`} data-reveal>
                <span className={styles.rule} data-rule><i /></span>
                <span className={styles.liNum}>{s.n}</span>
                <h3 className={styles.liTitle}>
                  {s.name}
                  {'experimental' in s && s.experimental && <span className={styles.exp}>Experimental</span>}
                </h3>
                <div className={styles.liBody}>
                  <p className={styles.liAbout}>{s.about}</p>
                  <p className={styles.liTrust}>{s.trust}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        {/* ── Bench band: the verdict legend and a recorded Overview sheet ── */}
        <section id="example" className={styles.band}>
          <div className={styles.legendWrap}>
            <div className={styles.legendHead}>
              <h2 className={styles.h2}>Colour means a verdict</h2>
              <p className={styles.bandNote}>
                Everything else is black, white and grey. Each colour travels with a glyph and a word.
              </p>
            </div>
            <ul className={`rule-grid ${styles.legend}`}>
              {LEGEND.map(({ v, tone, means }) => (
                <li key={v.word} className={styles.legendCell}>
                  <span className={`chip verdict chip-${tone}`}>
                    <span className="verdict-glyph" aria-hidden="true">{v.glyph}</span>
                    <span>{v.word}</span>
                  </span>
                  <span className={styles.legendMeans}>{means}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className={styles.exampleHead}>
            <h2 className={styles.h2}>Sheet 00, as the app draws it</h2>
            <p className={styles.bandNote}>
              A recorded example, not a live run: the room monitor, produced by the deterministic pipeline
              on {ROOM.recordedOn}. Every figure below is from that recording.
            </p>
          </div>

          <OverviewMiniature />
        </section>

        {/* ── Templates ───────────────────────────────────── */}
        <section id="templates" className={styles.templates}>
          <div className={styles.sectionHead}>
            <h2 className={styles.h2}>Templates</h2>
            <button type="button" className={styles.ctaSecondary} onClick={onGetStarted}>
              Open app →
            </button>
          </div>
          <div className={styles.cols}>
            {[
              TEMPLATES.filter((_, i) => i % 2 === 0),
              TEMPLATES.filter((_, i) => i % 2 === 1),
            ].map((col, c) => (
              <div key={c} className={c === 1 ? styles.colB : undefined}>
                {col.map((t) => (
                  <div key={t.label} className={`${styles.item} ${styles.reveal}`} data-reveal>
                    <button
                      type="button"
                      className={styles.panel}
                      style={{ aspectRatio: t.ratio }}
                      data-zoom
                      data-tooltip="Open the app"
                      onClick={onGetStarted}
                      aria-label={`${t.label} — open the app`}
                    >
                      <span className={styles.panelInner}>
                        <span className={styles.panelTags}>
                          <span>{t.outputs.join(' · ')}</span>
                          <span>recorded</span>
                        </span>
                        <span className={styles.panelLines}>
                          {t.lines.map(([k, v]) => (
                            <span key={k} className={styles.panelLine}>
                              <span className={styles.panelKey}>{k}</span>
                              <span>{v}</span>
                            </span>
                          ))}
                        </span>
                        <span className={styles.panelGrade}>
                          <span aria-hidden="true">✓</span> {t.verdict}
                        </span>
                      </span>
                    </button>
                    <h3 className={styles.itemTitle}>{t.label}</h3>
                    <p className={styles.itemDesc}>{t.desc}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        {/* ── Explanation ─────────────────────────────────── */}
        <section id="explanation" className={styles.explain}>
          <p className={`${styles.explainText} ${styles.big} ${styles.reveal}`} data-reveal>
            Running ngspice is the easy part. The explanation says what breaks if you change a
            value, and why.
          </p>
          <div className={`${styles.explainBlock} ${styles.reveal}`} data-reveal>
            <div className={styles.c}>{'// recorded explanation — room monitor, written by the derived explainer'}</div>
            <div><span className={styles.w}>R1 10 kΩ</span> — fast enough for 0.3 m of cable. Rise time ≈ 1.1 µs worst case; halving R1 halves it but doubles the 0.5 mA sunk while DATA is held low.</div>
            <div><span className={styles.w}>Q1</span> — needs 3 mA of base current (I_C/10) to saturate at V_CE ≤ 0.3 V; it gets at least 3.04 mA. Under-driven, it would sit in its linear region and heat.</div>
            <div><span className={styles.w}>R3 280 Ω</span> — the E96 value nearest 10 mA. Halving it would roughly double the current and, past 20 mA, overload the pin.</div>
          </div>
        </section>
      </main>

      {/* ── Footer (revealed from under main) ─────────────── */}
      <div className={styles.footerWrap}>
        <footer ref={footerRef} className={styles.footer}>
          <div className={styles.footerCols}>
            <div className={styles.fCol}>
              <span className={styles.rule} data-rule><i /></span>
              <span className={styles.fLabel}>Start</span>
              <button type="button" className={styles.fBtn} onClick={onGetStarted}>
                Generate your first circuit →
              </button>
              <div className={styles.fList}>
                <span>Describe it in plain English.</span>
                <span>Get the drawing set back, every claim graded.</span>
              </div>
            </div>
            <div className={styles.fCol}>
              <span className={styles.rule} data-rule><i /></span>
              <span className={styles.fLabel}>Elsewhere</span>
              <div className={styles.fList}>
                <a className={styles.ulink} href={DOCS_URL} target="_blank" rel="noopener noreferrer">Docs ↗</a>
                <a className={styles.ulink} href={REPO_URL} target="_blank" rel="noopener noreferrer">GitHub ↗</a>
                <a className={styles.ulink} href={DEMO_URL} target="_blank" rel="noopener noreferrer">Demo video ↗</a>
              </div>
            </div>
            <div className={styles.fCol}>
              <span className={styles.rule} data-rule><i /></span>
              <span className={styles.fLabel}>Status</span>
              <div className={styles.fList}>
                <span>Open source · AGPL-3.0</span>
                <span>Simulated and proved, not yet built or measured on a bench.</span>
                <span>PCB engine experimental.</span>
              </div>
            </div>
          </div>
          <div className={styles.footerBottom}>
            <span className={styles.footerMark}>
              <span className="tb-mark" aria-hidden="true" />
              <span className="t-wordmark">Circuit OS</span>
            </span>
            <span>© 2026 · AI hardware compiler</span>
          </div>
        </footer>
      </div>

      <span ref={tipRef} className={styles.tip} aria-hidden="true" />
    </div>
  )
}

/* ── A static miniature of the workbench's Overview sheet (OverviewSheet.tsx) ────────────────── */
function OverviewMiniature() {
  const r = ROOM
  const cells: { n: string; name: string; tone?: 'pass'; glyph?: string; status: string; detail: string }[] = [
    { n: '06', name: 'Rules', tone: 'pass', glyph: '✓', status: 'passed', detail: `${r.rules.errors} errors · ${r.rules.warnings} warnings` },
    { n: '06', name: 'Proofs', tone: 'pass', glyph: '✓', status: `proven ${r.properties.proven} of ${r.properties.total}`, detail: r.properties.signed ? 'signed' : 'not signed' },
    { n: '04', name: 'Simulation', tone: 'pass', glyph: '✓', status: 'passed', detail: `ngspice operating point · ${r.simulation.durationMs} ms` },
    { n: '03', name: 'Firmware', tone: 'pass', glyph: '✓', status: r.firmware.status, detail: r.firmware.board },
    { n: '05', name: 'BOM', status: `${r.bomLines} lines`, detail: 'prices dated, with their source' },
    { n: '01', name: 'Schematic', status: `${r.components} components`, detail: `${r.nets} nets · net labels` },
  ]
  const counters = [
    { tone: 'pass', glyph: '✓', word: 'Holds', n: r.claims.holds },
    { tone: 'warn', glyph: '~', word: 'Holds, defeasible', n: r.claims.defeasible },
    { tone: 'fail', glyph: '✕', word: 'Fails', n: r.claims.fails },
    { tone: 'none', glyph: '–', word: 'Not assessed / out of scope', n: r.claims.open },
  ] as const

  return (
    <figure className={styles.mini} aria-label="A recorded Overview sheet: the room monitor">
      <div className={styles.miniTop}>
        <span className={styles.miniBrand}>
          <span className="tb-mark" aria-hidden="true" />
          <span className="t-wordmark">Circuit OS</span>
        </span>
        <span className={styles.miniIntent}>{r.intent}</span>
        <span className={styles.miniChips}>
          <Chip mono>REV v{r.version}</Chip>
          <Chip mono className={styles.hideSm}>{r.generator}</Chip>
          <Chip mono className={styles.hideSm}>{r.targetMcu}</Chip>
        </span>
        <span className={styles.miniDemo}>
          <Chip tone="warn" label>
            Demo<span className={styles.hideSm}>&nbsp;— recorded results</span>
          </Chip>
        </span>
      </div>

      <div className={styles.miniTabs} aria-hidden="true">
        {[['00', 'Overview'], ['01', 'Schematic'], ['03', 'Firmware'], ['04', 'Simulation'], ['05', 'BOM'], ['06', 'Validation']].map(([n, l], i) => (
          <span key={n} className={i === 0 ? `${styles.miniTab} ${styles.miniTabOn}` : styles.miniTab}>
            <span className={styles.miniTabNum}>{n}</span>{l}
          </span>
        ))}
        <span className={styles.miniTabsFill} />
      </div>

      <div className={styles.miniHead}>
        <span className="t-label">Sheet 00</span>
        <span className={styles.miniHeadTitle}>Overview</span>
        <span className={styles.miniHeadMeta}>Compile report · revision {r.version}</span>
      </div>

      <div className={styles.miniBody}>
        <p className="t-label">Requirement</p>
        <p className={styles.miniTitle}>{r.intent}</p>
        <dl className={styles.miniMeta}>
          <div><dt className="t-label">Class</dt><dd>{r.applicationClass}</dd></div>
          <div><dt className="t-label">Board</dt><dd>{r.targetMcu}</dd></div>
          <div><dt className="t-label">Rev</dt><dd>v{r.version}</dd></div>
          <div><dt className="t-label">Generator</dt><dd>{r.generator}</dd></div>
          <div><dt className="t-label">Design</dt><dd className={styles.fg2}>{r.circuitId}</dd></div>
        </dl>

        <div className={`rule-grid ${styles.miniStrip}`}>
          {counters.map((c) => (
            <div key={c.word} className={styles.miniCounter}>
              <span className="t-label">{c.word}</span>
              <span className={`${styles.miniCounterNum} c-${c.tone}`}>
                <span className="t-display">{c.n}</span>
                <span className={styles.miniGlyph} aria-hidden="true">{c.glyph}</span>
              </span>
            </div>
          ))}
        </div>
        <div className={`rule-grid ${styles.miniFacts}`}>
          <div className={styles.miniFact}>
            <span className="t-label">Grade floor</span>
            <span className={styles.miniFactBody}><GradeChip grade={r.gradeFloor} /></span>
          </div>
          <div className={styles.miniFact}>
            <span className="t-label">Open defeaters</span>
            <span className={styles.miniFactBody}>{r.openDefeaters.map((d) => <Chip key={d} mono>{d}</Chip>)}</span>
          </div>
          <div className={styles.miniFact}>
            <span className="t-label">Proved properties</span>
            <span className={styles.miniFactBody}>
              <span className="t-data">proven {r.properties.proven} of {r.properties.total}</span>
              <Chip label tone="none">{r.properties.signed ? 'signed' : 'not signed'}</Chip>
            </span>
          </div>
        </div>

        <p className={`t-label ${styles.miniPipeLabel}`}>Pipeline</p>
        <div className={`rule-grid ${styles.miniPipe}`}>
          {cells.map((c) => (
            <div key={c.name} className={styles.miniCell}>
              <span className="t-label">{c.n} · {c.name}</span>
              <span className={`${styles.miniCellStatus} ${c.tone ? `c-${c.tone}` : ''}`}>
                {c.glyph && <span className="t-data" aria-hidden="true">{c.glyph}</span>}
                {c.status}
              </span>
              <span className={styles.miniCellDetail}>{c.detail}</span>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.miniStatus}>
        <span className={styles.sbCell}><span className={styles.sbK}>Design</span><span className={styles.sbV}>{r.circuitId.slice(0, 8)}</span></span>
        <span className={styles.sbCell}><span className={styles.sbK}>Rev</span><span className={styles.sbV}>v{r.version}</span></span>
        <span className={styles.sbCell}><span className={styles.sbK}>Rules</span><span className="c-pass">✓</span><span className={styles.sbV}>{r.rules.errors} errors · {r.rules.warnings} warnings</span></span>
        <span className={`${styles.sbCell} ${styles.sbOpt}`}>
          <span className={styles.sbK}>Claims</span>
          <span className="c-pass">{r.claims.holds} ✓</span>
          <span className="c-warn">{r.claims.defeasible} ~</span>
          <span className="c-fail">{r.claims.fails} ✕</span>
          <span className="c-none">{r.claims.open} –</span>
        </span>
        <span className={styles.sbCell}><span className={styles.sbK}>Grade floor</span><span className={styles.sbV}>{r.gradeFloor}</span></span>
        <span className={`${styles.sbCell} ${styles.sbOpt}`}><span className={styles.sbK}>Firmware</span><span className="c-pass">{r.firmware.status}</span></span>
        <span className={styles.sbFill} />
        <span className={styles.sbMode}>DEMO</span>
      </div>
      <figcaption className={styles.srOnly}>
        A recorded example of the Overview sheet for the room monitor. {r.claims.holds} claims hold,{' '}
        {r.claims.defeasible} hold defeasibly, {r.claims.fails} fail, {r.claims.open} are not assessed or out of scope.
      </figcaption>
    </figure>
  )
}
