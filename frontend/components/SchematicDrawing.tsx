'use client'

/**
 * The schematic, drawn from the design's CircuitIR and made to be explored:
 *  - point at a net (a label, a wire, or its chip above the drawing) and every
 *    pin on it lights up, with a dashed trace between them; click to keep it;
 *  - click a part for what it is, what each pin is on, and why it is there
 *    (the generator's own justification, carried in the IR).
 *
 * It draws what the IR says and nothing else: lib/schematicLayout.ts only
 * places parts, and every IR connection is one `data-pin` dot here. The
 * `.kicad_sch` file itself is one click away in the same window.
 */

import { useMemo, useRef, useState, KeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import {
  layoutSchematic, partLabel, readIr,
  BODY_W, FLAG_H, LEAD,
  type Box, type Flag, type IrComponent, type TwoPin,
} from '@/lib/schematicLayout'

interface Finding { field: string; message: string }
interface Props {
  ir: unknown
  findings?: Finding[]
}

type View = { x: number; y: number; w: number; h: number }

export default function SchematicDrawing({ ir: raw, findings = [] }: Props) {
  const ir = useMemo(() => readIr(raw), [raw])
  const layout = useMemo(() => (ir ? layoutSchematic(ir) : null), [ir])

  const [hoverNet, setHoverNet] = useState<string | null>(null)
  const [keptNet, setKeptNet] = useState<string | null>(null)
  const [part, setPart] = useState<string | null>(null)
  const [view, setView] = useState<View | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const pan = useRef<{ x: number; y: number } | null>(null)

  if (!ir || !layout) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        No design data to draw. The KiCad file is still available.
      </div>
    )
  }

  const full: View = { x: 0, y: 0, w: layout.width, h: layout.height }
  const v = view ?? full
  const net = hoverNet ?? keptNet
  const nodeOf = new Map(ir.nodes.map(n => [n.id, n]))
  const pinsOn = (id: string) => layout.pins.filter(p => p.net === id)
  const netFinding = (id: string) => findings.find(f => f.field === `nodes.${id}`)
  const chosen = part ? ir.components.find(c => c.id === part) ?? null : null

  const touches = (comp: string) => !net || layout.pins.some(p => p.comp === comp && p.net === net)
  const dim = (on: boolean) => (on ? 1 : 0.28)

  const keep = (id: string) => setKeptNet(k => (k === id ? null : id))
  const onKey = (act: () => void) => (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act() }
  }

  // The dashed trace: the net's pins joined in reading order.
  const trace = net
    ? pinsOn(net).slice().sort((p, q) => p.y - q.y || p.x - q.x).map(p => `${p.x},${p.y}`).join(' ')
    : ''

  const zoom = (factor: number) => {
    const w = Math.max(layout.width * 0.2, Math.min(layout.width * 2, v.w * factor))
    const h = w * (layout.height / layout.width)
    setView({ x: v.x + (v.w - w) / 2, y: v.y + (v.h - h) / 2, w, h })
  }
  const onPanDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest('[data-hit]')) return
    pan.current = { x: e.clientX, y: e.clientY }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onPanMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!pan.current || !svg) return
    const scale = Math.max(v.w / (svg.clientWidth || 1), v.h / (svg.clientHeight || 1))
    setView({ ...v, x: v.x - (e.clientX - pan.current.x) * scale, y: v.y - (e.clientY - pan.current.y) * scale })
    pan.current = { x: e.clientX, y: e.clientY }
  }
  const onPanUp = () => { pan.current = null }

  const netProps = (id: string, pins: number) => ({
    'data-hit': true,
    role: 'button',
    tabIndex: 0,
    'aria-pressed': keptNet === id,
    'aria-label': `Net ${id}, ${pins} pin${pins === 1 ? '' : 's'}`,
    onPointerEnter: () => setHoverNet(id),
    onPointerLeave: () => setHoverNet(null),
    onFocus: () => setHoverNet(id),
    onBlur: () => setHoverNet(null),
    onClick: () => keep(id),
    onKeyDown: onKey(() => keep(id)),
    style: { cursor: 'pointer' },
  })
  const partProps = (c: IrComponent) => ({
    'data-hit': true,
    'data-part': c.id,
    role: 'button',
    tabIndex: 0,
    'aria-pressed': part === c.id,
    'aria-label': `${c.id}, ${c.type}${partLabel(c) ? `, ${partLabel(c)}` : ''}`,
    onClick: () => setPart(p => (p === c.id ? null : c.id)),
    onKeyDown: onKey(() => setPart(p => (p === c.id ? null : c.id))),
    style: { cursor: 'pointer', opacity: dim(touches(c.id)) },
  })

  return (
    <div className="h-full flex flex-col min-h-0" data-testid="schematic-drawing">
      {/* Nets: one chip each. The same hover and click as the labels in the drawing. */}
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 border-b border-border/30">
        <span className="font-pixel text-lg leading-none mr-1">NETS</span>
        {ir.nodes.map(n => {
          const count = pinsOn(n.id).length
          const warn = netFinding(n.id)
          const on = net === n.id
          return (
            <button
              key={n.id}
              type="button"
              data-net-chip={n.id}
              aria-pressed={keptNet === n.id}
              title={warn ? warn.message : `${n.type ?? 'net'}${n.voltage_nominal != null ? ` · ${n.voltage_nominal} V` : ''}`}
              onPointerEnter={() => setHoverNet(n.id)}
              onPointerLeave={() => setHoverNet(null)}
              onFocus={() => setHoverNet(n.id)}
              onBlur={() => setHoverNet(null)}
              onClick={() => keep(n.id)}
              className={`min-h-[28px] px-2 font-mono text-xs border-[1.5px] ${
                on ? 'bg-lavender text-dark border-lavender'
                   : warn ? 'border-dashed border-warn text-warn' : 'border-border text-cream'
              }`}
            >
              {n.id} <span className={on ? '' : 'text-muted'}>{count}</span>
            </button>
          )
        })}
        <span className="flex-1" />
        <button type="button" onClick={() => zoom(0.8)} aria-label="Zoom in"
                className="w-7 h-7 border-[1.5px] border-border font-mono text-sm">+</button>
        <button type="button" onClick={() => zoom(1.25)} aria-label="Zoom out"
                className="w-7 h-7 border-[1.5px] border-border font-mono text-sm">−</button>
        <button type="button" onClick={() => setView(null)}
                className="h-7 px-2 border-[1.5px] border-border font-mono text-xs">Fit</button>
      </div>

      <svg
        ref={svgRef}
        viewBox={`${v.x} ${v.y} ${v.w} ${v.h}`}
        preserveAspectRatio="xMidYMid meet"
        role="group"
        aria-label={`Schematic: ${ir.components.length} parts, ${ir.nodes.length} nets`}
        className="flex-1 min-h-0 w-full font-mono select-none touch-none cursor-grab active:cursor-grabbing"
        onPointerDown={onPanDown}
        onPointerMove={onPanMove}
        onPointerUp={onPanUp}
        onPointerCancel={onPanUp}
      >
        {net && trace && (
          <polyline points={trace} fill="none" className="stroke-lavender" strokeWidth={1.5}
                    strokeDasharray="5 4" strokeLinejoin="round" data-testid="net-trace" />
        )}

        {layout.joints.map((j, i) => {
          const on = net === j.net
          return (
            <g key={`j${i}`} {...netProps(j.net, pinsOn(j.net).length)} opacity={dim(!net || on)}>
              <line x1={j.x1} y1={j.y} x2={j.x2} y2={j.y} className={on ? 'stroke-lavender' : 'stroke-cream'}
                    strokeWidth={on ? 2.5 : 1.5} />
              <rect x={j.x1} y={j.y - 22} width={j.x2 - j.x1} height={30} fill="transparent" />
              <text x={(j.x1 + j.x2) / 2} y={j.y - 8} textAnchor="middle" fontSize={11}
                    className={on ? 'fill-lavender' : 'fill-muted'}>{j.net}</text>
            </g>
          )
        })}

        {layout.boxes.map(b => <BoxSymbol key={b.comp.id} box={b} chosen={part === b.comp.id} props={partProps(b.comp)} />)}
        {layout.twoPins.map(t => <TwoPinSymbol key={t.comp.id} part={t} chosen={part === t.comp.id} props={partProps(t.comp)} />)}

        {layout.flags.map((f, i) => (
          <FlagMark key={`f${i}`} flag={f} on={net === f.net} faded={!!net && net !== f.net}
                    kind={nodeOf.get(f.net)?.type ?? ''} warn={!!netFinding(f.net)}
                    props={netProps(f.net, pinsOn(f.net).length)} />
        ))}

        {/* One dot per IR connection: the drawing's claim to completeness. */}
        {layout.pins.map(p => (
          <circle key={`${p.comp}.${p.pin}`} cx={p.x} cy={p.y} r={net === p.net ? 3.5 : 2}
                  data-pin={`${p.comp}.${p.pin}`} data-net={p.net}
                  className={net === p.net ? 'fill-lavender' : 'fill-cream'}
                  opacity={dim(!net || net === p.net)} />
        ))}
      </svg>

      <div className="border-t border-border/30 px-4 py-3 text-sm max-h-[38%] overflow-y-auto" data-testid="schematic-detail" aria-live="polite">
        {chosen ? (
          <PartDetail part={chosen} pins={layout.pins.filter(p => p.comp === chosen.id)} keptNet={keptNet} onNet={keep}
                      finding={findings.find(f => f.field === `components.${chosen.id}`)} />
        ) : keptNet ? (
          <div className="flex flex-col gap-1">
            <p>
              <strong className="font-semibold">{keptNet}</strong>
              <span className="text-muted">
                {' '}· {nodeOf.get(keptNet)?.type ?? 'net'}
                {nodeOf.get(keptNet)?.voltage_nominal != null ? ` · ${nodeOf.get(keptNet)!.voltage_nominal} V nominal` : ''}
              </span>
            </p>
            <p className="font-mono text-xs">{pinsOn(keptNet).map(p => `${p.comp}.${p.pin}`).join('   ') || 'no pins'}</p>
            {netFinding(keptNet) && <p className="text-warn">{netFinding(keptNet)!.message}</p>}
          </div>
        ) : (
          <p className="text-muted">
            Point at a net to trace it; click to keep it lit. Click a part to see what it is and why it is there.
          </p>
        )}
      </div>
    </div>
  )
}

type HitProps = Record<string, unknown>

function Title({ x, y, comp }: { x: number; y: number; comp: IrComponent }) {
  return (
    <text x={x} y={y} textAnchor="middle" fontSize={12} className="fill-cream">
      <tspan fontWeight={700}>{comp.id}</tspan>
      {partLabel(comp) && <tspan className="fill-muted"> {partLabel(comp)}</tspan>}
    </text>
  )
}

function BoxSymbol({ box, chosen, props }: { box: Box; chosen: boolean; props: HitProps }) {
  return (
    <g {...props}>
      <Title x={box.x + box.w / 2} y={box.y - 9} comp={box.comp} />
      <rect x={box.x} y={box.y} width={box.w} height={box.h} className={`fill-vast ${chosen ? 'stroke-lavender' : 'stroke-cream'}`}
            strokeWidth={chosen ? 3 : 1.5} />
      {box.pins.map(p => (
        <g key={p.pin}>
          <line x1={p.innerX} y1={p.y} x2={p.x} y2={p.y} className="stroke-cream" strokeWidth={1.5} />
          <text x={p.side === 'left' ? p.innerX + 7 : p.innerX - 7} y={p.y + 4} fontSize={11}
                textAnchor={p.side === 'left' ? 'start' : 'end'} className="fill-cream">{p.pin}</text>
        </g>
      ))}
    </g>
  )
}

function TwoPinSymbol({ part, chosen, props }: { part: TwoPin; chosen: boolean; props: HitProps }) {
  const { x, y, comp } = part
  const x0 = x + LEAD                  // body, left
  const x1 = x0 + BODY_W               // body, right
  const cx = (x0 + x1) / 2
  const stroke = chosen ? 'stroke-lavender' : 'stroke-cream'
  const sw = chosen ? 2.5 : 1.5
  let body
  if (comp.type === 'resistor') {
    body = (
      <>
        <line x1={x} y1={y} x2={x0} y2={y} className={stroke} strokeWidth={sw} />
        <rect x={x0} y={y - 9} width={BODY_W} height={18} className={`fill-vast ${stroke}`} strokeWidth={sw} />
        <line x1={x1} y1={y} x2={x1 + LEAD} y2={y} className={stroke} strokeWidth={sw} />
      </>
    )
  } else if (comp.type === 'capacitor') {
    body = (
      <>
        <line x1={x} y1={y} x2={cx - 5} y2={y} className={stroke} strokeWidth={sw} />
        <line x1={cx - 5} y1={y - 14} x2={cx - 5} y2={y + 14} className={stroke} strokeWidth={sw + 1} />
        <line x1={cx + 5} y1={y - 14} x2={cx + 5} y2={y + 14} className={stroke} strokeWidth={sw + 1} />
        <line x1={cx + 5} y1={y} x2={x1 + LEAD} y2={y} className={stroke} strokeWidth={sw} />
      </>
    )
  } else if (comp.type === 'led' || comp.type === 'diode') {
    // The anode is the pin named for it; the symbol points from anode to cathode.
    const anodeFirst = /^(a|anode|\+)$/i.test(part.a.pin) || !/^(a|anode|\+)$/i.test(part.b.pin)
    const tip = anodeFirst ? cx + 11 : cx - 11
    const base = anodeFirst ? cx - 11 : cx + 11
    body = (
      <>
        <line x1={x} y1={y} x2={x1 + LEAD} y2={y} className={stroke} strokeWidth={sw} />
        <polygon points={`${base},${y - 12} ${base},${y + 12} ${tip},${y}`} className={`fill-vast ${stroke}`} strokeWidth={sw} />
        <line x1={tip} y1={y - 12} x2={tip} y2={y + 12} className={stroke} strokeWidth={sw} />
        {comp.type === 'led' && (
          <>
            <line x1={cx + 2} y1={y - 16} x2={cx + 9} y2={y - 23} className={stroke} strokeWidth={1.2} />
            <line x1={cx + 10} y1={y - 14} x2={cx + 17} y2={y - 21} className={stroke} strokeWidth={1.2} />
          </>
        )}
      </>
    )
  } else {
    body = (
      <>
        <line x1={x} y1={y} x2={x0} y2={y} className={stroke} strokeWidth={sw} />
        <rect x={x0} y={y - 13} width={BODY_W} height={26} rx={3} className={`fill-vast ${stroke}`} strokeWidth={sw} />
        <text x={cx} y={y + 4} textAnchor="middle" fontSize={10} className="fill-muted">{comp.type}</text>
        <line x1={x1} y1={y} x2={x1 + LEAD} y2={y} className={stroke} strokeWidth={sw} />
      </>
    )
  }
  return (
    <g {...props}>
      <rect x={x} y={y - 30} width={part.w} height={48} fill="transparent" />
      <Title x={cx} y={y - (comp.type === 'led' ? 28 : 19)} comp={comp} />
      {body}
      <text x={x0 - 3} y={y + 17} textAnchor="end" fontSize={9} className="fill-muted">{part.a.pin}</text>
      <text x={x1 + 3} y={y + 17} textAnchor="start" fontSize={9} className="fill-muted">{part.b.pin}</text>
    </g>
  )
}

function FlagMark({ flag, on, faded, kind, warn, props }: {
  flag: Flag; on: boolean; faded: boolean; kind: string; warn: boolean; props: HitProps
}) {
  const y = flag.y - FLAG_H / 2
  const solid = kind === 'power'
  const box = on ? 'fill-lavender stroke-lavender'
    : warn ? 'fill-vast stroke-warn'
    : solid ? 'fill-cream stroke-cream'
    : kind === 'ground' ? 'fill-surface-2 stroke-cream' : 'fill-vast stroke-cream'
  const text = on || solid ? 'fill-dark' : warn ? 'fill-warn' : 'fill-cream'
  return (
    <g {...props} data-net-flag={flag.net} opacity={faded ? 0.28 : 1}>
      <rect x={flag.x} y={y} width={flag.w} height={FLAG_H} className={box} strokeWidth={1.5}
            strokeDasharray={warn && !on ? '4 3' : undefined} />
      <text x={flag.x + flag.w / 2} y={flag.y + 4} textAnchor="middle" fontSize={11} className={text}>
        {flag.net}
      </text>
    </g>
  )
}

function PartDetail({ part, pins, keptNet, onNet, finding }: {
  part: IrComponent
  pins: { pin: string; net: string }[]
  keptNet: string | null
  onNet: (id: string) => void
  finding?: Finding
}) {
  const facts = [
    ['Value', partLabel(part) && part.type !== 'microcontroller' && partLabel(part) !== part.part_number ? partLabel(part) : null],
    ['Part number', part.part_number],
    ['Maker', part.manufacturer],
    ['Package', part.package],
  ].filter(([, value]) => !!value) as [string, string][]
  return (
    <div className="flex flex-col gap-2">
      <p>
        <strong className="font-semibold text-base">{part.id}</strong>
        <span className="text-muted"> · {part.type}</span>
      </p>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs">
        {facts.map(([label, value]) => (
          <div key={label} className="flex gap-2">
            <dt className="text-muted">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs text-muted">Pins</span>
        {pins.map(p => (
          <button key={p.pin} type="button" onClick={() => onNet(p.net)} aria-pressed={keptNet === p.net}
                  className={`min-h-[26px] px-2 font-mono text-xs border-[1.5px] ${
                    keptNet === p.net ? 'bg-lavender text-dark border-lavender' : 'border-border'}`}>
            {p.pin} → {p.net}
          </button>
        ))}
      </div>
      {part.justification && <p className="max-w-[78ch] leading-relaxed">{part.justification}</p>}
      {finding && <p className="text-warn">{finding.message}</p>}
    </div>
  )
}
