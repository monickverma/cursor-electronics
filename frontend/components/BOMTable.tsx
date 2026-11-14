'use client'

/**
 * Sheet 05 — BOM. Dated prices, a part priced only as itself, one total per currency (never
 * converted), and — with a design id and a token — the checked substitutes for each line.
 * A price is not a verdict: an unknown one is grey. Only the substitutes' re-proved checks are green.
 */
import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Download } from 'lucide-react'

import { applyPatchOps, BOMRow, BOMView, CurrencyTotal, getBom, PatchResponse, Substitute } from '@/lib/api'
import { Button, Callout, Chip, Cursor, EmptyState, ICON, Section, SheetFrame, VerdictBadge } from '@/components/ui'

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

// The price a row shows, in its own currency: a live quote's, else the
// catalogue's USD. Never converted ([2026-09-25]).
function shown(r: BOMRow): { price: number; currency: string } | null {
  if (!isPriced(r)) return null
  if (r.unit_price != null && r.currency) return { price: r.unit_price, currency: r.currency }
  return { price: r.unit_price_usd, currency: 'USD' }
}

function money(v: number | null | undefined, currency = 'USD', digits?: number): string {
  if (v === null || v === undefined) return '—'
  const d = digits ?? (Math.abs(v) < 1 ? 4 : 2)
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency, minimumFractionDigits: d, maximumFractionDigits: d,
    }).format(v)
  } catch {
    return `${v.toFixed(d)} ${currency}`
  }
}

function asOf(r: BOMRow): string {
  if (!isPriced(r)) return '—'
  if (r.live) return `${r.live.fetched_at.slice(0, 16).replace('T', ' ')} UTC`
  return r.price_asof ?? 'undated'
}

// One total per currency — a mixed BOM shows two totals, not a converted sum.
function rowTotals(rows: BOMRow[]): CurrencyTotal[] {
  const by = new Map<string, CurrencyTotal>()
  for (const r of rows) {
    const s = shown(r)
    if (!s) continue
    const t = by.get(s.currency) ?? { currency: s.currency, amount: 0, rows: 0, sources: [] }
    t.amount += s.price * r.quantity
    t.rows += 1
    const source = r.price_source ?? 'unknown'
    if (!t.sources.includes(source)) t.sources.push(source)
    by.set(s.currency, t)
  }
  return Array.from(by.values())
}

function totalsText(totals: CurrencyTotal[]): string {
  return totals.length ? totals.map(t => money(t.amount, t.currency, 2)).join(' + ') : money(0, 'USD', 2)
}

// Mouser's own storefronts. The host is matched whole, never by prefix:
// mouser.evil.example and www.mouser.com.attacker.net are not Mouser.
const MOUSER_DOMAINS = new Set([
  'mouser.com', 'mouser.co.uk', 'mouser.de', 'mouser.fr', 'mouser.it', 'mouser.es', 'mouser.ch',
  'mouser.at', 'mouser.be', 'mouser.nl', 'mouser.dk', 'mouser.se', 'mouser.fi', 'mouser.pl',
  'mouser.cz', 'mouser.ie', 'mouser.pt', 'mouser.in', 'mouser.jp', 'mouser.cn', 'mouser.kr',
  'mouser.tw', 'mouser.hk', 'mouser.sg', 'mouser.ca', 'mouser.com.au', 'mouser.co.il', 'mouser.com.br',
])

// Only a Mouser product page is linked; anything else in the field stays text.
function mouserLink(url: string | null | undefined): string | null {
  if (!url) return null
  let u: URL
  try {
    u = new URL(url)
  } catch {
    return null
  }
  const host = u.hostname.toLowerCase().replace(/^www\./, '')
  return u.protocol === 'https:' && !u.username && !u.password && MOUSER_DOMAINS.has(host) ? url : null
}

const COLUMNS: { label: string; num?: boolean }[] = [
  { label: 'Ref' }, { label: 'Part number' }, { label: 'Manufacturer' }, { label: 'Package' },
  { label: 'Value' }, { label: 'Qty', num: true }, { label: 'LCSC' }, { label: 'Unit', num: true },
  { label: 'Line total', num: true }, { label: 'Price as of' }, { label: 'Source' },
]
// The footer's label spans everything before "Line total"; the amount sits under it.
const LABEL_SPAN = 8

export default function BOMTable({ rows: initialRows, circuitId, version, token, onPatched }: Props) {
  const [view, setView] = useState<BOMView | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [applying, setApplying] = useState<string | null>(null)
  const [showRejected, setShowRejected] = useState(false)

  useEffect(() => {
    if (!circuitId || !token) return
    let cancelled = false
    // The previous version's view is not this version's: never show it, nor offer its substitutes.
    setView(null)
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
      <SheetFrame meta={loading ? 'Loading…' : undefined}>
        {loading ? (
          <p className="t-ui c-fg-2"><Cursor label="Loading" /> Loading the bill of materials…</p>
        ) : (
          <EmptyState title="BOM not available.">This design has no bill of materials.</EmptyState>
        )}
      </SheetFrame>
    )
  }

  const totals = view?.totals ?? rowTotals(rows)
  const unpriced = rows.filter(r => !isPriced(r))
  const byComponent = new Map<string, Substitute[]>()
  for (const s of view?.substitutes ?? []) {
    byComponent.set(s.component_id, [...(byComponent.get(s.component_id) ?? []), s])
  }
  const rejected = view?.rejected ?? []
  const subCount = view?.substitutes?.length ?? 0
  const pricingError = view?.live_pricing?.error ?? null
  const cacheError = view?.live_pricing?.cache_error ?? null

  function handleExportCSV() {
    const header = [
      'ID', 'Part Number', 'Manufacturer', 'Package', 'Value', 'Qty',
      'LCSC PN', 'Unit Price', 'Total', 'Currency', 'Price as of', 'Price Source', 'Mouser PN',
    ].join(',')
    const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
    const body = rows.map(r => {
      const s = shown(r)
      return [
        r.id,
        esc(r.part_number),
        esc(r.manufacturer),
        r.package,
        r.value || '',
        String(r.quantity),
        r.lcsc_pn || '',
        s ? s.price.toFixed(4) : '',
        s ? (s.price * r.quantity).toFixed(4) : '',
        s ? s.currency : '',
        r.price_asof || '',
        r.price_source || '',
        r.live?.distributor_pn || '',
      ].join(',')
    }).join('\n')

    const blob = new Blob([header + '\n' + body], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'circuit_os_bom.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const meta = (
    <>
      <span className="t-data">{rows.length}</span> components ·{' '}
      {unpriced.length === 0 ? 'estimated total' : 'partial total'}{' '}
      <span className="t-data c-fg">{totalsText(totals)}</span>
      {unpriced.length > 0 && <> · <span className="t-data">{unpriced.length}</span> unpriced</>}
    </>
  )

  return (
    <SheetFrame
      padded={false}
      meta={meta}
      actions={
        <Button size="sm" icon={<Download {...ICON} />} onClick={handleExportCSV}>Export CSV</Button>
      }
    >
      {(view?.pricing || pricingError || cacheError) && (
        <div className="px-4 py-2 border-b border-line flex flex-col gap-2">
          {view?.pricing && <p className="t-small c-fg-3 max-w-[110ch]">{view.pricing}</p>}
          {(pricingError || cacheError) && (
            <Callout tone="info" title="Live prices fell back to the static catalogue">
              {pricingError && <span className="t-small block">{pricingError}</span>}
              {cacheError && <span className="t-small block">Price cache: {cacheError}</span>}
            </Callout>
          )}
        </div>
      )}

      <table className="dt dt-inset" data-testid="bom-table">
        <thead>
          <tr>
            {COLUMNS.map(c => (
              <th key={c.label} scope="col" className={c.num ? 'num' : undefined}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const price = shown(row)
            const link = mouserLink(row.live?.product_url)
            const title = priceTitle(row)
            return (
              <tr key={i}>
                <td className="mono whitespace-nowrap">{row.id}</td>
                <td className="mono whitespace-nowrap">{row.part_number}</td>
                <td className="c-fg-2 whitespace-nowrap">{row.manufacturer}</td>
                <td className="mono c-fg-2 whitespace-nowrap">{row.package}</td>
                <td className="mono whitespace-nowrap">{row.value || <span className="muted">—</span>}</td>
                <td className="num">{row.quantity}</td>
                <td className="mono whitespace-nowrap">
                  {row.lcsc_pn ? row.lcsc_pn : <span className="muted">—</span>}
                </td>
                <td className="num whitespace-nowrap" title={title}>
                  {price ? money(price.price, price.currency) : <span className="muted">unknown</span>}
                </td>
                <td className="num whitespace-nowrap">
                  {price ? money(price.price * row.quantity, price.currency) : <span className="muted">unknown</span>}
                </td>
                <td className={`mono whitespace-nowrap ${price ? 'c-fg-2' : 'muted'}`} title={title}>{asOf(row)}</td>
                <td className="whitespace-nowrap" title={title}>
                  {row.live ? (
                    <span className="inline-flex items-center gap-2">
                      <Chip>
                        {link
                          ? <a href={link} target="_blank" rel="noopener noreferrer" className="link">Mouser</a>
                          : 'Mouser'}
                        <span className="c-fg-3">{row.live.currency}</span>
                      </Chip>
                      {row.live.stock != null && (
                        <span className="t-small c-fg-3" title={`${row.live.stock.toLocaleString('en-US')} in stock`}>
                          <span className="t-data">
                            {new Intl.NumberFormat('en-US', { notation: 'compact' }).format(row.live.stock)}
                          </span> in stock
                        </span>
                      )}
                    </span>
                  ) : price ? (
                    <Chip>catalogue</Chip>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot data-testid="bom-total">
          {(totals.length ? totals : [{ currency: 'USD', amount: 0, rows: 0, sources: [] }]).map((t, i) => (
            <tr key={t.currency}>
              <td colSpan={LABEL_SPAN} className="text-right c-fg-2">
                <span className="t-label">
                  {i === 0 && unpriced.length > 0 ? 'Partial total' : 'Total'} · {t.currency}
                </span>
                {i === 0 && totals.length > 1 && (
                  <span className="t-small c-fg-3"> — one per currency, not converted</span>
                )}
              </td>
              <td className="num whitespace-nowrap">{money(t.amount, t.currency, 2)}</td>
              <td colSpan={2} className="t-small c-fg-3 whitespace-nowrap">
                {t.rows > 0 && <><span className="t-data">{t.rows}</span> {t.rows === 1 ? 'row' : 'rows'}</>}
              </td>
            </tr>
          ))}
          {unpriced.length > 0 && (
            <tr>
              <td colSpan={LABEL_SPAN} className="text-right">
                <span className="t-label">Unpriced · {unpriced.length}</span>
              </td>
              <td colSpan={3} className="mono c-fg-3">{unpriced.map(r => r.id).join(', ')}</td>
            </tr>
          )}
        </tfoot>
      </table>

      {circuitId && token && (
        <div className="px-4 pt-8 pb-12" data-testid="bom-substitutes">
          <Section label="Substitutes" count={view && !view.substitutes_unavailable ? subCount : undefined}>
            <p className="t-small c-fg-2 max-w-[78ch] mb-4">
              Each part below passed every check the original passed — its claims re-derived and the
              original&apos;s proved properties re-proved over its own tolerance and ratings. Using one is a
              patch to the requirement: a new version, and a signed design must be signed again.
            </p>
            <div className="flex flex-col gap-3">
              {loading && <p className="t-small c-fg-2"><Cursor label="Checking" /> Checking substitutes…</p>}
              {error && <Callout tone="fail" role="alert">{error}</Callout>}
              {view?.substitutes_unavailable && <Callout tone="info">{view.substitutes_unavailable}</Callout>}
              {view && !view.substitutes_unavailable && byComponent.size === 0 && !loading && (
                <p className="t-small c-fg-3">No catalogue part passes the original&apos;s checks for any line.</p>
              )}
            </div>

            {Array.from(byComponent.entries()).map(([cid, subs]: [string, Substitute[]]) => (
              <div key={cid} className="mt-6 first:mt-0">
                <div className="flex items-baseline gap-2 pb-2">
                  <span className="t-data c-fg">{cid}</span>
                  <span className="t-label">replaces</span>
                  <span className="t-data c-fg-2">{subs[0].replaces}</span>
                </div>
                <ul className="border-t border-line">
                  {subs.map(s => {
                    const key = `${s.component_id}:${s.part_number}`
                    const figures = s.changes.slice(1)
                    return (
                      <li
                        key={key}
                        className="flex flex-col gap-3 py-3 border-b border-line sm:flex-row sm:items-start sm:justify-between"
                      >
                        <div className="min-w-0 flex flex-col gap-1">
                          <div className="flex flex-wrap items-baseline gap-2">
                            <span className="t-data c-fg">{s.part_number}</span>
                            <span className="t-data c-fg-3">{s.package}</span>
                          </div>
                          <div className="t-data c-fg-2">{figures.join(' · ') || 'same figures'}</div>
                          <div className="t-small c-fg-3">
                            {s.unit_price_usd != null
                              ? <>
                                  <span className="t-data">{money(s.unit_price_usd)}</span> as of{' '}
                                  <span className="t-data">{s.price_asof}</span>
                                  {s.price_delta_usd != null && (
                                    <span className="t-data">
                                      {' '}({s.price_delta_usd >= 0 ? '+' : ''}{s.price_delta_usd.toFixed(4)})
                                    </span>
                                  )}
                                </>
                              : 'price unknown'}
                            {s.live && (
                              <> · Mouser <span className="t-data">{money(s.live.unit_price, s.live.currency)}</span></>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 flex-none">
                          <VerdictBadge tone="pass" label={`${s.checks} checks passed`} />
                          <Button
                            size="sm"
                            onClick={() => apply(s)}
                            disabled={applying !== null || loading}
                          >
                            {applying === key ? <><Cursor /> Applying…</> : 'Use this part'}
                          </Button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}

            {rejected.length > 0 && (
              <div className="mt-6">
                <button
                  type="button"
                  className="disclosure t-small c-fg-2 hover:text-fg h-7"
                  aria-expanded={showRejected}
                  onClick={() => setShowRejected(o => !o)}
                >
                  {showRejected
                    ? <ChevronDown size={12} strokeWidth={1.5} aria-hidden />
                    : <ChevronRight size={12} strokeWidth={1.5} aria-hidden />}
                  <span>{rejected.length} checked and not offered — why</span>
                </button>
                {showRejected && (
                  <ul className="mt-2 border border-dashed border-line-2">
                    {rejected.map(r => (
                      <li
                        key={`${r.component_id}:${r.part_number}`}
                        className="flex flex-col gap-1 px-3 py-2 border-b border-dashed border-line-2 last:border-b-0 t-small c-fg-3 sm:flex-row sm:gap-4"
                      >
                        {/* The reason is the li's own text, not a second element: a search for the
                            part number then finds one element (the reason names the part too). */}
                        <span className="t-data c-fg-2 flex-none sm:w-56">
                          {r.component_id} {r.part_number}
                        </span>
                        {r.reason}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </Section>
        </div>
      )}
    </SheetFrame>
  )
}
