'use client'

import { useEffect, useRef } from 'react'
import { Inter_Tight } from 'next/font/google'
import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import styles from './LandingPage.module.css'

// One family, three weights — the study site uses GT Standard (licensed); Inter Tight is the free stand-in.
const landingFont = Inter_Tight({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'block',
  variable: '--font-landing',
})

interface Props {
  onGetStarted: () => void
}

const DEMO_URL =
  'https://drive.google.com/drive/folders/1GkFsTZ7xmXJsFuvLrNU-J_l4yDbeylfo?usp=sharing'

const TEMPLATES = [
  {
    label: 'DHT22 Sensor',
    desc: 'Temperature & humidity monitoring with relay alert above configurable threshold.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    simLines: ['VCC    5.0000V  ✓', 'GND    0.0000V  ✓', 'DATA   3.3000V  ✓'],
    grade: 'DC operating point — PASS',
    ratio: '5 / 4',
  },
  {
    label: 'RS-485 Modbus',
    desc: 'MAX485 transceiver, Modbus RTU master, 9600 baud. Bias + termination resistors included.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    simLines: ['RS485_A  2.5000V  ✓', 'RS485_B  2.5000V  ✓', 'DE_RE    5.0000V  ✓'],
    grade: 'RS-485 termination — PASS',
    ratio: '4 / 3',
  },
  {
    label: 'LED Control',
    desc: 'Current-limiting resistor for GPIO-driven LED. Arduino Uno PWM or digital output.',
    outputs: ['Schematic', 'Firmware', 'Simulation', 'BOM'],
    simLines: ['LED_A   4.3500V  ✓', 'LED_K   0.0000V  ✓', 'I_LED   18.2mA  ✓'],
    grade: 'DC operating point — PASS',
    ratio: '1 / 1',
  },
  {
    label: 'RC Filter',
    desc: '1590Ω + 100nF → 1kHz low-pass cutoff. ngspice AC sweep validates -3dB point.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    simLines: ['f=1001Hz  Vout=0.707V  ✓', 'f=500Hz   Vout=0.894V  ✓', 'f=2kHz    Vout=0.447V  ✓'],
    grade: 'AC sweep -3dB @ 1001 Hz — PASS',
    ratio: '5 / 4',
  },
  {
    label: 'Voltage Divider',
    desc: '12V → 5V output. DC operating point analysis confirms node voltages within 15%.',
    outputs: ['Schematic', 'Simulation', 'BOM'],
    simLines: ['VIN   12.0000V  ✓', 'VOUT   5.0400V  ✓', 'GND    0.0000V  ✓'],
    grade: 'DC operating point — PASS',
    ratio: '1 / 1',
  },
]

const FEATURES = [
  {
    title: 'Physics simulation',
    desc: 'ngspice AC/DC analysis runs on every design. A 15% tolerance gate stops a bad design before you order parts.',
  },
  {
    title: 'KiCad schematic',
    desc: 'Net-label .kicad_sch output you can open immediately in KiCad. No manual net assignment.',
  },
  {
    title: 'Arduino firmware',
    desc: 'Deterministic Jinja2 templates, built with PlatformIO. Firmware is shown only once it compiles.',
  },
  {
    title: 'Component BOM',
    desc: 'Every row matches the design. Prices are dated catalogue prices, or a live Mouser quote when configured — a price never gates a validation.',
  },
  {
    title: 'AI explanation',
    desc: 'Every component explained with the consequences of changing it: "If you change R1 from 10k to 4.7k, here is what breaks."',
  },
  {
    title: 'Patch & edit',
    desc: 'Change a value in plain English. The requirement is edited and the design re-derived through the same checks; a change that cannot be justified is refused and the previous version is kept.',
  },
]

const PIPELINE = [
  { step: 'Parsing intent via tool_use', done: true },
  { step: 'Requirement → IntentIR', done: true },
  { step: 'Structural validation', done: true },
  { step: 'SPICE netlist compiler', done: true },
  { step: 'Arduino firmware (Jinja2)', done: true },
  { step: 'KiCad schematic (net labels)', done: true },
  { step: 'BOM compiler', done: true },
  { step: 'Simulation queued → Celery', done: false },
]

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
    document.body.style.background = '#000'
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
    <div ref={rootRef} className={`${landingFont.variable} ${styles.root}`}>
      {/* ── Nav ───────────────────────────────────────────── */}
      <nav ref={navRef} className={styles.nav} aria-label="Primary">
        <span className={styles.navBrand}>circuit os</span>
        <span className={styles.navGroup}>
          <a href="#templates" className={styles.ulink}>templates</a>
          <a href="#included" className={styles.ulink}>included</a>
          <a href="#explanation" className={styles.ulink}>explanation</a>
        </span>
        <span className={styles.navTag}>ai hardware compiler</span>
        <span className={styles.navCta}>
          <button type="button" className={`${styles.navButton} ${styles.ulink}`} onClick={onGetStarted}>
            open app
          </button>
        </span>
      </nav>

      {/* ── Hero ──────────────────────────────────────────── */}
      <section ref={heroRef} className={styles.hero}>
        <div ref={zoomRef} className={styles.heroZoom}>
          <div className={`${styles.heroTerminal} ${styles.mono}`} aria-hidden="true">
            <div>$ describe &quot;DHT22 alert above 30°C&quot;</div>
            {PIPELINE.map((p, i) => (
              <div key={p.step} className={p.done ? styles.done : styles.live}>
                {p.done ? '✓' : '⟳'} {i + 1}. {p.step}
              </div>
            ))}
          </div>

          <div className={styles.heroBottom}>
            <div className={`${styles.heroMeta} ${styles.small}`}>
              <span>AI hardware compiler</span>
              <span>Plain English in. Schematic, firmware, simulation and BOM out.</span>
            </div>
            <h1 className={styles.heroTitle}>
              Don&apos;t draw,
              <br />
              just describe.
            </h1>
          </div>
        </div>
      </section>

      {/* ── Main (white) ──────────────────────────────────── */}
      <main ref={mainRef} className={styles.main}>
        <section className={styles.statement}>
          <span className={`${styles.statementLabel} ${styles.small} ${styles.reveal}`} data-reveal>
            AI hardware compiler
          </span>
          <p className={`${styles.statementText} ${styles.big} ${styles.reveal}`} data-reveal>
            Circuit OS turns a plain-English description into a validated schematic, firmware that
            compiles, a SPICE simulation and a bill of materials — before a single part is ordered.
          </p>
        </section>

        <section className={styles.vision}>
          <span className={styles.rule} data-rule><i /></span>
          <span className={`${styles.visionLabel} ${styles.small} ${styles.reveal}`} data-reveal>
            Principle
          </span>
          <div className={styles.visionBody}>
            <p className={`${styles.normal} ${styles.reveal}`} data-reveal>
              The language model never writes SPICE, KiCad files or firmware. It writes a structured
              description of the requirement, and deterministic compilers turn that into every
              output. The same requirement gives the same design, and a request that cannot be
              justified is refused instead of negotiated. That is why a result can say what was
              checked, and what was not.
            </p>
            <div className={`${styles.rows} ${styles.normal}`}>
              <div className={styles.row}>
                <span className={styles.rule} data-rule><i /></span>
                <button type="button" className={styles.cta} onClick={onGetStarted}>
                  <span>Open the app</span>
                  <span aria-hidden="true">→</span>
                  <span className={styles.ctaLines}><i className={styles.ctaLine1} /><i className={styles.ctaLine2} /></span>
                </button>
              </div>
              <div className={styles.row}>
                <a className={styles.cta} href={DEMO_URL} target="_blank" rel="noopener noreferrer">
                  <span>Demo video</span>
                  <span aria-hidden="true">→</span>
                  <span className={styles.ctaLines}><i className={styles.ctaLine1} /><i className={styles.ctaLine2} /></span>
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ── Templates ───────────────────────────────────── */}
        <section id="templates" className={styles.templates}>
          <div className={`${styles.sectionHead} ${styles.normal}`} style={{ padding: 0 }}>
            <h2>Templates</h2>
            <button type="button" className={styles.ctaSecondary} onClick={onGetStarted}>
              Open the app →
            </button>
          </div>
          <div className={styles.cols}>
            {[
              TEMPLATES.filter((_, i) => i % 2 === 0),
              TEMPLATES.filter((_, i) => i % 2 === 1),
            ].map((col, c) => (
              <div key={c} className={c === 1 ? styles.colB : undefined}>
                {col.map((t) => (
                  <div key={t.label} className={`${styles.item} ${styles.normal} ${styles.reveal}`} data-reveal>
                    <button
                      type="button"
                      className={styles.panel}
                      style={{ aspectRatio: t.ratio }}
                      data-zoom
                      data-tooltip="Open the app"
                      onClick={onGetStarted}
                      aria-label={`${t.label} — open the app`}
                    >
                      <span className={`${styles.panelInner} ${styles.mono}`}>
                        <span className={styles.panelTags}>{t.outputs.join(' · ')}</span>
                        <span className={styles.panelLines}>
                          {t.simLines.map((l) => (
                            <span key={l}>{l}</span>
                          ))}
                        </span>
                        <span className={styles.panelGrade}>✓ {t.grade}</span>
                      </span>
                    </button>
                    <h3>{t.label}</h3>
                    <p>{t.desc}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        {/* ── Included ────────────────────────────────────── */}
        <section id="included" className={styles.included}>
          <div className={`${styles.sectionHead} ${styles.normal}`} style={{ padding: 0 }}>
            <h2>Included</h2>
            <span className={styles.grey}>One prompt, one workflow</span>
          </div>
          <ul className={styles.list}>
            {FEATURES.map((f, i) => (
              <li key={f.title} className={`${styles.li} ${styles.normal} ${styles.reveal}`} data-reveal>
                <span className={styles.rule} data-rule><i /></span>
                <span className={styles.liNum}>{String(i + 1).padStart(2, '0')}</span>
                <h3 className={styles.liTitle}>{f.title}</h3>
                <p className={styles.liDesc}>{f.desc}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* ── Explanation ─────────────────────────────────── */}
        <section id="explanation" className={styles.explain}>
          <p className={`${styles.explainText} ${styles.big} ${styles.reveal}`} data-reveal>
            Any engineer can run ngspice. What no tool does is tell you exactly what breaks if you
            change a value — and why. The explanation is the product.
          </p>
          <div className={`${styles.explainBlock} ${styles.mono} ${styles.reveal}`} data-reveal>
            <div className={styles.c}>{'// example explanation — DHT22 circuit, component R1'}</div>
            <div className={styles.w}>R1 (10kΩ) pulls the DHT22 DATA line high between transmissions.</div>
            <div className={styles.warn}>⚠ Without R1: the open-drain output never reaches logic HIGH.</div>
            <div className={styles.warn}>⚠ Every read returns a timeout. The MCU loops indefinitely.</div>
            <div>Lowering R1 below 1kΩ pushes the line current past a 5mA sink limit at 5V.</div>
            <div>At 1kΩ: 5mA, on the limit. At 10kΩ: 0.5mA, well inside it.</div>
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
                <span>Get a physics-validated design back.</span>
              </div>
            </div>
            <div className={styles.fCol}>
              <span className={styles.rule} data-rule><i /></span>
              <span className={styles.fLabel}>Elsewhere</span>
              <div className={styles.fList} style={{ marginTop: 0 }}>
                <a className={styles.ulink} href={DEMO_URL} target="_blank" rel="noopener noreferrer">
                  Demo video
                </a>
              </div>
            </div>
            <div className={styles.fCol}>
              <span className={styles.rule} data-rule><i /></span>
              <span className={styles.fLabel}>Status</span>
              <div className={styles.fList} style={{ marginTop: 0 }}>
                <span>Phase 1 · v0.1.0-rc · MIT</span>
              </div>
            </div>
          </div>
          <div className={styles.footerBottom}>
            <span>© 2026 Circuit OS</span>
            <span>AI hardware compiler</span>
          </div>
        </footer>
      </div>

      <span ref={tipRef} className={styles.tip} aria-hidden="true" />
    </div>
  )
}
