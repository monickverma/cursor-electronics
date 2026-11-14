'use client'

/**
 * A plain SVG line chart for simulation sweeps. Stage 3 waveform viewer.
 *
 * No chart library: one component, the design tokens, and nothing to update.
 * Every point drawn is a real ngspice sample (backend/simulation/waveforms.py
 * strides long sweeps but never interpolates), and a missing sample breaks the
 * line instead of being drawn as zero — 0 V is a reading, a gap is not.
 *
 * Monochrome (spec §6): the first trace is white at 1.5px; further traces are
 * told apart by dash pattern and by a label at the end of each line, and the
 * legend repeats the dash patterns. The SVG is drawn at the width it is given
 * (one SVG unit = one CSS pixel), so tick text stays legible at any width.
 */

import { useEffect, useRef, useState, type CSSProperties } from 'react'
import type { Sweep } from '@/lib/api'

const H = 280
const PAD = { left: 60, top: 12, bottom: 28 }
const DASHES = ['', '6 4', '2 3', '10 3 2 3', '1 5', '14 6']

// The legend swatch repeats a trace's dash pattern in CSS rather than as a second <svg>:
// the figure holds exactly one <svg>, the chart, which is what a reader (and a test) looks for.
function swatch(color: string, dash: string): CSSProperties {
  const base: CSSProperties = { display: 'inline-block', width: 24, height: 1.5, flexShrink: 0 }
  if (!dash) return { ...base, background: color }
  const stops: string[] = []
  let x = 0
  dash.split(' ').map(Number).forEach((len, i) => {
    stops.push(`${i % 2 === 0 ? color : 'transparent'} ${x}px ${x + len}px`)
    x += len
  })
  return { ...base, background: `repeating-linear-gradient(90deg, ${stops.join(', ')})` }
}
const MONO = 'var(--font-mono)'
const LABEL_CH = 6.6   // px per mono character at 10.5px

const PREFIXES: Array<[number, string]> = [[1e9, 'G'], [1e6, 'M'], [1e3, 'k'], [1, ''], [1e-3, 'm'], [1e-6, 'µ'], [1e-9, 'n']]

/** A value in engineering notation, split into the number and the prefixed unit. */
export function siParts(value: number, unit: string): [string, string] {
  if (value === 0 || !Number.isFinite(value)) return ['0', unit]
  const abs = Math.abs(value)
  const [scale, prefix] = PREFIXES.find(([s]) => abs >= s) ?? PREFIXES[PREFIXES.length - 1]
  return [`${parseFloat((value / scale).toPrecision(3))}`, `${prefix}${unit}`]
}

export function si(value: number, unit: string): string {
  const [n, u] = siParts(value, unit)
  return `${n} ${u}`
}

/** A 1 / 2 / 5 step that divides `range` into about `count` intervals. */
function niceStep(range: number, count: number): number {
  const raw = range / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / mag
  return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag
}

function linearTicks(lo: number, hi: number, step: number): number[] {
  const out: number[] = []
  const first = Math.ceil(lo / step - 1e-9)
  for (let i = first; i * step <= hi + step * 1e-9; i++) out.push(Number((i * step).toPrecision(12)))
  return out
}

interface Props {
  sweep: Sweep
  logX?: boolean
  xUnit: string
  yUnit: string
  title: string
}

const QUANTITY: Record<string, string> = { Hz: 'Frequency', s: 'Time', V: 'Voltage', A: 'Current' }

export default function WaveformChart({ sweep, logX = false, xUnit, yUnit, title }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [W, setW] = useState(720)
  useEffect(() => {
    const el = box.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(entries => {
      const w = Math.floor(entries[0].contentRect.width)
      if (w > 0) setW(Math.max(260, w))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const names = Object.keys(sweep.series)
  const xs = sweep.x
  const usable = xs.length > 1 && names.length > 0 && (!logX || xs.every(x => x > 0))
  const xName = `${QUANTITY[xUnit] ?? 'x'} · ${xUnit}${logX ? ', log' : ''}`
  const yName = `${QUANTITY[yUnit] ?? 'y'} · ${yUnit}`

  if (!usable) {
    return (
      <figure className="border border-line">
        <figcaption className="flex items-center h-8 px-3 border-b border-line">
          <span className="t-label text-fg">{title}</span>
        </figcaption>
        <div className="m-3 border border-dashed border-line-2 px-4 py-6 text-fg-2">
          No samples to plot for this sweep.
        </div>
      </figure>
    )
  }

  const fx = (x: number) => (logX ? Math.log10(x) : x)
  const xMin = fx(xs[0])
  const xMax = fx(xs[xs.length - 1])
  const values = names.flatMap(n => sweep.series[n]).filter((v): v is number => v !== null && Number.isFinite(v))
  let lo = Math.min(0, ...values)
  let hi = Math.max(...values)
  if (hi === lo) { hi += 1; lo -= 1 }
  const yStep = niceStep(hi - lo, 5)
  const yMin = Math.floor(lo / yStep + 1e-9) * yStep
  const yMax = Math.ceil(hi / yStep - 1e-9) * yStep

  const labelWidth = Math.max(...names.map(n => `v(${n})`.length)) * LABEL_CH
  const right = Math.round(labelWidth + 16)
  const plotW = W - PAD.left - right
  const px = (x: number) => PAD.left + ((fx(x) - xMin) / (xMax - xMin || 1)) * plotW
  const py = (y: number) => H - PAD.bottom - ((y - yMin) / (yMax - yMin)) * (H - PAD.top - PAD.bottom)

  // Ticks: decades on a log axis (with minor lines at 2…9), 1/2/5 steps on a linear one.
  const decades = Array.from({ length: Math.floor(xMax + 1e-9) - Math.ceil(xMin - 1e-9) + 1 }, (_, i) => 10 ** (Math.ceil(xMin - 1e-9) + i))
  const xTicks = logX
    ? decades
    : linearTicks(xs[0], xs[xs.length - 1], niceStep(xs[xs.length - 1] - xs[0], Math.max(2, Math.floor(plotW / 110))))
  const minor = logX && decades.length <= 10
    ? Array.from({ length: Math.ceil(xMax) - Math.floor(xMin) }, (_, d) => 10 ** (Math.floor(xMin) + d))
        .flatMap(base => [2, 3, 4, 5, 6, 7, 8, 9].map(k => base * k))
        .filter(x => fx(x) > xMin && fx(x) < xMax)
    : []
  // On a narrow chart, label every other decade so the tick text never collides.
  const everyX = logX && decades.length * 44 > plotW ? 2 : 1
  const yTicks = linearTicks(yMin, yMax, yStep)

  // Split each series at gaps so a missing sample is never drawn as a line.
  const segments = (ys: Array<number | null>) => {
    const out: string[] = []
    let current: string[] = []
    ys.forEach((y, i) => {
      if (y === null || !Number.isFinite(y)) {
        if (current.length > 1) out.push(current.join(' '))
        current = []
      } else {
        current.push(`${px(xs[i]).toFixed(1)},${py(y).toFixed(1)}`)
      }
    })
    if (current.length > 1) out.push(current.join(' '))
    return out
  }

  // A direct label at the end of each line, pushed apart so two never overlap.
  const ends = names.map((name, n) => {
    const ys = sweep.series[name]
    let i = ys.length - 1
    while (i >= 0 && (ys[i] === null || !Number.isFinite(ys[i] as number))) i--
    return { name, n, y: i >= 0 ? py(ys[i] as number) : py(yMin) }
  }).sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 12) ends[i].y = ends[i - 1].y + 12

  const stroke = (n: number) => (n === 0 ? 'var(--fg)' : 'var(--fg-2)')

  return (
    <figure className="border border-line" data-testid={`waveform-${title}`}>
      <figcaption className="flex items-center gap-3 h-8 px-3 border-b border-line">
        <span className="t-label text-fg">{title}</span>
        <span className="ml-auto t-data text-fg-3">{xs.length} samples</span>
      </figcaption>
      <div className="px-3 pt-3 pb-2">
        <p className="t-label mb-2">{yName}</p>
        <div ref={box} className="w-full">
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="block" role="img"
               aria-label={`${title}: ${names.join(', ')} against ${xUnit}`}>
            {minor.map((t, i) => (
              <line key={`m${i}`} x1={px(t)} x2={px(t)} y1={PAD.top} y2={H - PAD.bottom}
                    stroke="var(--line)" strokeWidth={1} strokeOpacity={0.5} shapeRendering="crispEdges" />
            ))}
            {yTicks.map((t, i) => (
              <g key={`y${i}`}>
                <line x1={PAD.left} x2={PAD.left + plotW} y1={py(t)} y2={py(t)}
                      stroke={t === 0 ? 'var(--line-2)' : 'var(--line)'} strokeWidth={1} shapeRendering="crispEdges" />
                <text x={PAD.left - 8} y={py(t) + 3.5} textAnchor="end" fill="var(--fg-3)"
                      fontFamily={MONO} fontSize={10.5}>{si(t, yUnit)}</text>
              </g>
            ))}
            {xTicks.map((t, i) => (
              <g key={`x${i}`}>
                <line x1={px(t)} x2={px(t)} y1={PAD.top} y2={H - PAD.bottom}
                      stroke="var(--line)" strokeWidth={1} shapeRendering="crispEdges" />
                {i % everyX === 0 && (
                  <text x={px(t)} y={H - PAD.bottom + 16} textAnchor="middle" fill="var(--fg-3)"
                        fontFamily={MONO} fontSize={10.5}>{si(t, xUnit)}</text>
                )}
              </g>
            ))}
            <rect x={PAD.left} y={PAD.top} width={plotW} height={H - PAD.top - PAD.bottom}
                  fill="none" stroke="var(--line-2)" strokeWidth={1} shapeRendering="crispEdges" />
            {names.map((name, n) => segments(sweep.series[name]).map((pts, s) => (
              <polyline key={`${name}-${s}`} points={pts} fill="none"
                        stroke={stroke(n)} strokeWidth={1.5} strokeDasharray={DASHES[n % DASHES.length] || undefined}
                        strokeLinejoin="round" />
            )))}
            {ends.map(e => (
              <text key={`l-${e.name}`} x={PAD.left + plotW + 6} y={e.y + 3.5} fill={stroke(e.n)}
                    fontFamily={MONO} fontSize={10.5}>v({e.name})</text>
            ))}
          </svg>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1">
          {names.map((name, n) => (
            <span key={name} className="inline-flex items-center gap-2 t-data text-fg-2">
              <span aria-hidden="true" style={swatch(stroke(n), DASHES[n % DASHES.length])} />
              v({name})
            </span>
          ))}
          <span className="ml-auto t-label">{xName}</span>
        </div>
      </div>
    </figure>
  )
}
