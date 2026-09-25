'use client'

import { useCallback, useEffect, useState } from 'react'

import { applyPatchOps, BOMRow, BOMView, getBom, PatchResponse, Substitute } from '@/lib/api'

interface Props {
  rows: BOMRow[]
  // Stage 6: with a design id and a token the table reads GET /design/{id}/bom —
  // dated prices and each line's checked substitutes — and can apply one.
  circuitId?: string
  version?: number
  token?: string
  onPatched?: (res: PatchResponse) => void
}

// A row is unpriced when the part is absent from component_db.json.
// Older API responses omit `price_known`, so fall back to the price itself.
function isPriced(r: BOMRow): boolean {
  return r.price_known ?? r.unit_price_usd > 0
}

function priceTitle(r: BOMRow): string | undefined {
  if (!isPriced(r)) return 'Not in the parts catalogue as this exact part — price unknown'
  return r.price_note ?? undefined
}

function money(v: number | null | undefined, digits = 4): string {
  return v === null || v === undefined ? '—' : `$${v.toFixed(digits)}`
}

export default function BOMTable({ rows: initialRows, circuitId, version, token, onPatched }: Props) {
  const [view, setView] = useState<BOMView | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [applying, setApplying] = useState<string | null>(null)

  useEffect(() => {
    if (!circuitId || !token) return
    let cancelled = false
    setLoading(true)
    setError(null)
    getBom(circuitId, token)
      .then(v => { if (!cancelled) setView(v) })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [circuitId, version, token])

  const apply = useCallback(async (sub: Substitute) => {
    if (!circuitId || !token) return
    setApplying(`${sub.component_id}:${sub.part_number}`)
    setError(null)
    try {
      const res = await applyPatchOps(circuitId, sub.ops, token)
      onPatched?.(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setApplying(null)
    }
  }, [circuitId, token, onPatched])

  const rows = view?.rows ?? initialRows
  if (!rows || rows.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        {loading ? 'Loading the bill of materials…' : 'BOM not available.'}
      </div>
    )
  }

  const total = rows.reduce((sum, r) => sum + r.total_price_usd, 0)
  const unpriced = rows.filter(r => !isPriced(r))
  const byComponent = new Map<string, Substitute[]>()
  for (const s of view?.substitutes ?? []) {
    byComponent.set(s.component_id, [...(byComponent.get(s.component_id) ?? []), s])
  }
  const rejected = view?.rejected ?? []

  function handleExportCSV() {
    const header = [
      'ID', 'Part Number', 'Manufacturer', 'Package', 'Value', 'Qty',
      'LCSC PN', 'Unit Price (USD)', 'Total (USD)', 'Price as of', 'Price Source',
    ].join(',')
    const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
    const body = rows.map(r => [
      r.id,
      esc(r.part_number),
      esc(r.manufacturer),
      r.package,
      r.value || '',
      String(r.quantity),
      r.lcsc_pn || '',
      isPriced(r) ? r.unit_price_usd.toFixed(4) : '',
      isPriced(r) ? r.total_price_usd.toFixed(4) : '',
      r.price_asof || '',
      r.price_source || '',
    ].join(',')).join('\n')

    const blob = new Blob([header + '\n' + body], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'circuit_os_bom.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <span className="text-xs text-muted">
          {rows.length} components ·{' '}
          {unpriced.length === 0 ? 'Estimated total: ' : 'Partial total: '}
          <span className="text-lavender">${total.toFixed(2)} USD</span>
          {unpriced.length > 0 && (
            <span className="text-amber-400">
              {' '}· {unpriced.length} unpriced ({unpriced.map(r => r.id).join(', ')})
            </span>
          )}
        </span>
        <button
          onClick={handleExportCSV}
          className="text-xs text-lavender hover:text-lavender-dim transition-colors"
        >
          Export CSV
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm" data-testid="bom-table">
          <thead className="sticky top-0 bg-surface border-b border-border">
            <tr>
              {['ID', 'Part Number', 'Manufacturer', 'Package', 'Value', 'LCSC PN', 'Unit $', 'Total $', 'Price as of'].map(h => (
                <th key={h} className="text-left px-3 py-2 text-xs text-muted font-normal whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const priced = isPriced(row)
              return (
                <tr key={i} className="border-b border-border/50 hover:bg-surface/50 transition-colors">
                  <td className="px-3 py-2 font-mono text-xs text-lavender-dim">{row.id}</td>
                  <td className="px-3 py-2 text-xs font-medium text-cream">{row.part_number}</td>
                  <td className="px-3 py-2 text-xs text-muted">{row.manufacturer}</td>
                  <td className="px-3 py-2 text-xs text-muted font-mono">{row.package}</td>
                  <td className="px-3 py-2 text-xs text-muted font-mono">{row.value || '—'}</td>
                  <td className="px-3 py-2 text-xs">
                    {row.lcsc_pn ? (
                      <span className="text-lavender font-mono">{row.lcsc_pn}</span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-right font-mono text-cream-dim" title={priceTitle(row)}>
                    {priced ? `$${row.unit_price_usd.toFixed(2)}` : <span className="text-amber-400">unknown</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-right font-mono text-cream">
                    {priced ? `$${row.total_price_usd.toFixed(2)}` : <span className="text-amber-400">unknown</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted font-mono" title={priceTitle(row)}>
                    {priced ? (row.price_asof ?? 'undated') : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot className="border-t border-border bg-surface">
            <tr>
              <td colSpan={7} className="px-3 py-2 text-xs text-muted text-right">
                {unpriced.length > 0 ? `Total (${unpriced.length} unpriced)` : 'Total'}
              </td>
              <td className="px-3 py-2 text-xs font-medium text-right text-lavender font-mono">
                ${total.toFixed(2)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>

        {circuitId && token && (
          <section className="px-4 py-3 border-t border-border" data-testid="bom-substitutes">
            <h3 className="text-sm text-cream mb-1">Substitutes</h3>
            <p className="text-xs text-muted mb-3">
              Each part below passed every check the original passed — its claims re-derived and the
              original&apos;s proved properties re-proved over its own tolerance and ratings. Using one is a
              patch to the requirement: a new version, and a signed design must be signed again.
            </p>
            {loading && <p className="text-xs text-muted">Checking substitutes…</p>}
            {error && <p className="text-xs text-amber-400">{error}</p>}
            {view?.substitutes_unavailable && (
              <p className="text-xs text-amber-400">{view.substitutes_unavailable}</p>
            )}
            {view && !view.substitutes_unavailable && byComponent.size === 0 && !loading && (
              <p className="text-xs text-muted">No catalogue part passes the original&apos;s checks for any line.</p>
            )}
            {Array.from(byComponent.entries()).map(([cid, subs]: [string, Substitute[]]) => (
              <div key={cid} className="mb-3">
                <div className="text-xs text-lavender-dim font-mono mb-1">{cid} · {subs[0].replaces}</div>
                <ul className="space-y-1">
                  {subs.map(s => {
                    const key = `${s.component_id}:${s.part_number}`
                    return (
                      <li key={key} className="flex items-start justify-between gap-3 bg-surface border border-border rounded px-3 py-2">
                        <div className="text-xs">
                          <div className="text-cream font-mono">{s.part_number} <span className="text-muted">({s.package})</span></div>
                          <div className="text-muted">{s.changes.slice(1).join(' · ') || 'same figures'}</div>
                          <div className="text-muted">
                            {s.unit_price_usd != null
                              ? <>{money(s.unit_price_usd)} as of {s.price_asof}{s.price_delta_usd != null && ` (${s.price_delta_usd >= 0 ? '+' : ''}${s.price_delta_usd.toFixed(4)})`}</>
                              : 'price unknown'}
                            {' '}· {s.checks} checks passed
                          </div>
                        </div>
                        <button
                          onClick={() => apply(s)}
                          disabled={applying !== null}
                          className="text-xs bg-lavender text-dark px-2 py-1 rounded hover:bg-lavender-dim disabled:opacity-50 whitespace-nowrap"
                        >
                          {applying === key ? 'Applying…' : 'Use this part'}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
            {rejected.length > 0 && (
              <details className="text-xs text-muted">
                <summary className="cursor-pointer">{rejected.length} checked and not offered — why</summary>
                <ul className="mt-2 space-y-1">
                  {rejected.map(r => (
                    <li key={`${r.component_id}:${r.part_number}`}>
                      <span className="font-mono text-cream-dim">{r.component_id} {r.part_number}</span>: {r.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        )}
      </div>

      {view?.pricing && (
        <div className="px-4 py-2 border-t border-border bg-surface text-xs text-muted">{view.pricing}</div>
      )}
    </div>
  )
}
