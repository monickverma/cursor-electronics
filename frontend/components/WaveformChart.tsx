'use client'

/**
 * A plain SVG line chart for simulation sweeps. Stage 3 waveform viewer.
 *
 * No chart library: one component, the design tokens, and nothing to update.
 * Every point drawn is a real ngspice sample (backend/simulation/waveforms.py
 * strides long sweeps but never interpolates), and a missing sample breaks the
 * line instead of being drawn as zero — 0 V is a reading, a gap is not.
 */

import type { Sweep } from '@/lib/api'

const W = 640
const H = 260
const PAD = { left: 56, right: 16, top: 12, bottom: 36 }
const STROKES = ['stroke-lavender', 'stroke-glow', 'stroke-cream', 'stroke-green-400', 'stroke-sky-400', 'stroke-rose-400']
const SWATCH = ['bg-lavender', 'bg-glow', 'bg-cream', 'bg-green-400', 'bg-sky-400', 'bg-rose-400']

const PREFIXES: Array<[number, string]> = [[1e9, 'G'], [1e6, 'M'], [1e3, 'k'], [1, ''], [1e-3, 'm'], [1e-6, 'µ'], [1e-9, 'n']]

export function si(value: number, unit: string): string {
  if (value === 0 || !Number.isFinite(value)) return `0 ${unit}`
  const abs = Math.abs(value)
  const [scale, prefix] = PREFIXES.find(([s]) => abs >= s) ?? PREFIXES[PREFIXES.length - 1]
  return `${parseFloat((value / scale).toPrecision(3))} ${prefix}${unit}`
}

interface Props {
  sweep: Sweep
  logX?: boolean
  xUnit: string
  yUnit: string
  title: string
}

export default function WaveformChart({ sweep, logX = false, xUnit, yUnit, title }: Props) {
  const names = Object.keys(sweep.series)
  const xs = sweep.x
  const usable = xs.length > 1 && names.length > 0 && (!logX || xs.every(x => x > 0))
  if (!usable) {
    return <p className="text-sm text-muted">{title}: no samples to plot.</p>
  }

  const fx = (x: number) => (logX ? Math.log10(x) : x)
  const xMin = fx(xs[0])
  const xMax = fx(xs[xs.length - 1])
  const values = names.flatMap(n => sweep.series[n]).filter((v): v is number => v !== null && Number.isFinite(v))
  let yMin = Math.min(0, ...values)
  let yMax = Math.max(...values)
  if (yMax === yMin) { yMax += 1; yMin -= 1 }

  const px = (x: number) => PAD.left + ((fx(x) - xMin) / (xMax - xMin || 1)) * (W - PAD.left - PAD.right)
  const py = (y: number) => H - PAD.bottom - ((y - yMin) / (yMax - yMin)) * (H - PAD.top - PAD.bottom)

  const xTicks = logX
    ? Array.from({ length: Math.floor(xMax) - Math.ceil(xMin) + 1 }, (_, i) => 10 ** (Math.ceil(xMin) + i))
    : Array.from({ length: 5 }, (_, i) => xs[0] + (i / 4) * (xs[xs.length - 1] - xs[0]))
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + (i / 4) * (yMax - yMin))

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

  return (
    <figure className="bg-surface border border-border rounded p-3" data-testid={`waveform-${title}`}>
      <figcaption className="text-sm text-cream mb-2">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
           aria-label={`${title}: ${names.join(', ')} against ${xUnit}`}>
        {yTicks.map((t, i) => (
          <g key={`y${i}`}>
            <line x1={PAD.left} x2={W - PAD.right} y1={py(t)} y2={py(t)} className="stroke-border" strokeWidth={1} />
            <text x={PAD.left - 6} y={py(t) + 4} textAnchor="end" className="fill-muted" fontSize={10}>{si(t, yUnit)}</text>
          </g>
        ))}
        {xTicks.map((t, i) => (
          <g key={`x${i}`}>
            <line x1={px(t)} x2={px(t)} y1={PAD.top} y2={H - PAD.bottom} className="stroke-border" strokeWidth={1} />
            <text x={px(t)} y={H - PAD.bottom + 16} textAnchor="middle" className="fill-muted" fontSize={10}>{si(t, xUnit)}</text>
          </g>
        ))}
        {names.map((name, n) => segments(sweep.series[name]).map((pts, s) => (
          <polyline key={`${name}-${s}`} points={pts} fill="none" strokeWidth={1.75}
                    className={STROKES[n % STROKES.length]} />
        )))}
      </svg>
      <div className="flex flex-wrap gap-3 mt-2">
        {names.map((name, n) => (
          <span key={name} className="inline-flex items-center gap-1.5 text-xs font-mono text-muted">
            <span className={`inline-block w-3 h-0.5 ${SWATCH[n % SWATCH.length]}`} />v({name})
          </span>
        ))}
        <span className="text-xs text-muted ml-auto">{xs.length} samples{logX ? ', log frequency' : ''}</span>
      </div>
    </figure>
  )
}
