'use client'

/**
 * The parts sheet: every part in the design, with what its data says it is
 * rated for laid beside what this design puts on it, and the way to its
 * datasheet. It is the cross-check an engineer does by hand, part by part.
 *
 * It states figures; it gives no verdict. Whether a rating is respected is the
 * validator's claim to make (voltage_ratings_ok, under Validation), with a
 * grade — a second, ungraded "OK" here would be exactly the unchecked pass the
 * claims table exists to prevent. The one thing this sheet marks is plain
 * arithmetic: a nominal voltage above the part's stated maximum.
 *
 * Below it, the catalogue can be searched as you type. Finding a part adds it
 * to nothing: "Ask for this part" writes a request into the prompt bar, and the
 * change goes through the requirement like any other.
 */

import { useEffect, useMemo, useState } from 'react'
import { searchParts, type CataloguePart } from '@/lib/api'
import { DEMO_MODE } from '@/lib/demo'
import { partLabel, readIr, type IrComponent } from '@/lib/schematicLayout'

interface Rated extends IrComponent {
  supply_voltage_min?: number | null
  supply_voltage_max?: number | null
  current_draw_ma?: number | null
  operating_temp_min?: number | null
  operating_temp_max?: number | null
  lcsc_pn?: string | null
  digikey_pn?: string | null
}

interface Props {
  ir: unknown
  token: string
  /** Put a request in the prompt bar for the person to send. */
  onAsk: (request: string) => void
}

const num = (v: number) => String(Number(v.toPrecision(4)))
const datasheetSearch = (pn: string) => `https://www.google.com/search?q=${encodeURIComponent(`${pn} datasheet`)}`

export default function PartsSheet({ ir: raw, token, onAsk }: Props) {
  const ir = useMemo(() => readIr(raw), [raw])
  const [query, setQuery] = useState('')
  const [found, setFound] = useState<CataloguePart[] | null>(null)
  const [size, setSize] = useState<number | null>(null)
  const [error, setError] = useState('')

  // Search as the person types, a beat after they stop.
  useEffect(() => {
    if (DEMO_MODE || !token) return
    const q = query.trim()
    if (!q) { setFound(null); setError(''); return }
    let stale = false
    const timer = setTimeout(() => {
      searchParts(q, token)
        .then(r => { if (!stale) { setFound(r.results); setSize(r.catalogue_size); setError('') } })
        .catch(e => { if (!stale) setError(e instanceof Error ? e.message : 'The catalogue could not be searched.') })
    }, 180)
    return () => { stale = true; clearTimeout(timer) }
  }, [query, token])

  if (!ir) {
    return <div className="h-full flex items-center justify-center text-muted text-sm">No design data to list.</div>
  }

  const volts = new Map(ir.nodes.map(n => [n.id, n.voltage_nominal ?? null]))
  const rows = (ir.components as Rated[]).map(part => {
    const pins = ir.connections.filter(c => c.component_id === part.id)
    const nets = Array.from(new Set(pins.map(p => p.node_id)))
    // Ground is 0 V by definition: on its own it says nothing about what the part sees.
    const known = nets.map(n => volts.get(n)).filter((v): v is number => typeof v === 'number' && v > 0)
    const applied = known.length ? Math.max(...known) : null
    const vmax = part.supply_voltage_max ?? null
    return { part, nets, applied, vmax, over: applied !== null && vmax !== null && applied > vmax }
  })

  return (
    <div className="h-full overflow-y-auto" data-testid="parts-sheet">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm" data-testid="parts-table">
          <thead>
            <tr className="text-left text-muted border-b border-border">
              <th className="font-normal px-3 py-2">Part</th>
              <th className="font-normal px-3 py-2">Rated for</th>
              <th className="font-normal px-3 py-2">In this design</th>
              <th className="font-normal px-3 py-2">Look it up</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ part, nets, applied, vmax, over }) => (
              <tr key={part.id} className="align-top border-b border-border/30" data-part-row={part.id}>
                <td className="px-3 py-2">
                  <p><strong className="font-semibold">{part.id}</strong> <span className="text-muted">{part.type}</span></p>
                  <p className="font-mono text-xs">{part.part_number ?? 'no part number'}</p>
                  <p className="font-mono text-[11px] text-muted">
                    {[partLabel(part) !== part.part_number ? partLabel(part) : null, part.manufacturer, part.package]
                      .filter(Boolean).join(' · ')}
                  </p>
                </td>
                <td className="px-3 py-2 font-mono text-xs leading-relaxed">
                  {vmax !== null && (
                    <p>{part.supply_voltage_min != null ? `${num(part.supply_voltage_min)} to ` : 'up to '}{num(vmax)} V</p>
                  )}
                  {part.current_draw_ma != null && <p>{num(part.current_draw_ma)} mA here</p>}
                  {part.operating_temp_min != null && part.operating_temp_max != null && (
                    <p>{num(part.operating_temp_min)} to {num(part.operating_temp_max)} °C</p>
                  )}
                  {vmax === null && part.current_draw_ma == null && <p className="text-muted">nothing recorded</p>}
                </td>
                <td className="px-3 py-2 font-mono text-xs leading-relaxed">
                  <p>{nets.join(', ') || 'not connected'}</p>
                  {applied !== null ? (
                    <p className={over ? 'text-bad font-bold' : 'text-muted'}>
                      up to {num(applied)} V nominal
                      {vmax !== null && (over
                        ? ` — above its ${num(vmax)} V maximum`
                        : ` · ${Math.round((applied / vmax) * 100)}% of its ${num(vmax)} V`)}
                    </p>
                  ) : (
                    <p className="text-muted">no nominal voltage on its nets</p>
                  )}
                </td>
                <td className="px-3 py-2 text-xs">
                  {part.part_number ? (
                    <a href={datasheetSearch(part.part_number)} target="_blank" rel="noopener noreferrer"
                       className="underline underline-offset-2">Datasheet search</a>
                  ) : <span className="text-muted">—</span>}
                  {part.lcsc_pn && <p className="font-mono text-[11px] text-muted mt-0.5">LCSC {part.lcsc_pn}</p>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-2 text-xs text-muted leading-relaxed">
        Figures as the design records them; voltages are the nets&apos; nominal values. This sheet gives no verdict —
        whether a rating holds is graded under Validation.
      </p>

      {!DEMO_MODE && (
        <section aria-label="Parts catalogue" className="border-t border-border px-3 py-3 flex flex-col gap-2">
          <label htmlFor="parts-search" className="font-pixel text-lg leading-none">FIND A PART</label>
          <input
            id="parts-search"
            type="search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Type a part number, a value or a kind: 10k, 0402, DHT22, relay…"
            className="flow-field !min-h-[40px] !py-2 !text-xs"
          />
          {error && <p role="alert" className="text-xs text-bad">{error}</p>}
          {found !== null && found.length === 0 && !error && (
            <p className="text-xs text-muted">
              Nothing in the catalogue{size ? ` of ${size} parts` : ''} matches. A part outside it cannot be designed in yet.
            </p>
          )}
          {found !== null && found.length > 0 && (
            <ul className="flex flex-col" data-testid="parts-results">
              {found.map(p => (
                <li key={p.part_number} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 border-t border-border/30">
                  <div className="flex-[999_1_260px] min-w-0">
                    <p className="font-mono text-xs"><strong className="font-bold">{p.part_number}</strong>
                      <span className="text-muted"> {[p.category, p.package, p.manufacturer].filter(Boolean).join(' · ')}</span></p>
                    <p className="text-xs text-cream-dim">{p.description}</p>
                    {p.unit_price_usd != null && (
                      <p className="font-mono text-[11px] text-muted">
                        ${p.unit_price_usd} · catalogue price{p.price_asof ? `, ${p.price_asof}` : ''}
                      </p>
                    )}
                  </div>
                  <button type="button"
                          onClick={() => onAsk(`Use ${p.part_number}${p.description ? ` (${p.description})` : ''}`)}
                          className="flex-none min-h-[36px] px-3 border-[1.5px] border-border font-mono text-xs hover:bg-cream hover:text-dark">
                    Ask for this part
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
