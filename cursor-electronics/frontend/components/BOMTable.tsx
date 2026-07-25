'use client'

import { BOMRow } from '@/lib/api'

interface Props {
  rows: BOMRow[]
}

// A row is unpriced when the part is absent from component_db.json.
// Older API responses omit `price_known`, so fall back to the price itself.
function isPriced(r: BOMRow): boolean {
  return r.price_known ?? r.unit_price_usd > 0
}

// Explains where a price came from, shown as a tooltip on substituted rows.
function sourceNote(r: BOMRow): string | null {
  switch (r.price_source) {
    case 'equivalent_value':
      return `Priced from an electrically equivalent part: ${r.priced_as}`
    case 'part_number_prefix':
      return `Priced from the orderable part number: ${r.priced_as}`
    case 'unknown':
      return 'Not found in the component database — price unknown'
    default:
      return null
  }
}

export default function BOMTable({ rows }: Props) {
  if (!rows || rows.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        BOM not available.
      </div>
    )
  }

  const total = rows.reduce((sum, r) => sum + r.total_price_usd, 0)
  const unpriced = rows.filter(r => !isPriced(r))
  const substituted = rows.filter(
    r => r.price_source === 'equivalent_value' || r.price_source === 'part_number_prefix'
  )

  function handleExportCSV() {
    const header = [
      'ID', 'Part Number', 'Manufacturer', 'Package', 'Value', 'Qty',
      'LCSC PN', 'Unit Price (USD)', 'Total (USD)', 'Price Source', 'Priced As',
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
      r.price_source || '',
      r.priced_as || '',
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
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface border-b border-border">
            <tr>
              {['ID', 'Part Number', 'Manufacturer', 'Package', 'Value', 'LCSC PN', 'Unit $', 'Total $'].map(h => (
                <th key={h} className="text-left px-3 py-2 text-xs text-muted font-normal whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const priced = isPriced(row)
              const note = sourceNote(row)
              return (
                <tr key={i} className="border-b border-border/50 hover:bg-surface/50 transition-colors">
                  <td className="px-3 py-2 font-mono text-xs text-lavender-dim">{row.id}</td>
                  <td className="px-3 py-2 text-xs font-medium text-cream">
                    {row.part_number}
                    {row.priced_as && row.priced_as !== row.part_number && (
                      <span className="ml-1.5 text-muted font-normal" title={note ?? undefined}>
                        ≈ {row.priced_as}
                      </span>
                    )}
                  </td>
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
                  <td className="px-3 py-2 text-xs text-right font-mono text-cream-dim">
                    {priced ? (
                      `$${row.unit_price_usd.toFixed(2)}`
                    ) : (
                      <span className="text-amber-400" title={note ?? undefined}>unknown</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-right font-mono text-cream">
                    {priced ? (
                      `$${row.total_price_usd.toFixed(2)}`
                    ) : (
                      <span className="text-amber-400">unknown</span>
                    )}
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
            </tr>
          </tfoot>
        </table>
      </div>

      {substituted.length > 0 && (
        <div className="px-4 py-2 border-t border-border bg-surface text-xs text-muted">
          {substituted.length} price{substituted.length === 1 ? '' : 's'} taken from an
          equivalent database part (marked ≈). Verify the exact part before ordering.
        </div>
      )}
    </div>
  )
}
