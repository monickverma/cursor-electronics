'use client'

/**
 * EVIDENCE_CLASSES Table A — the design claim summary. Stage 3.
 *
 * Two disciplines the table exists to keep:
 *  - every claim is its own row with its own grade — never a document grade;
 *  - "not assessed" and "out of scope" are printed rows, not omissions.
 *    What was not checked is part of the finding. Nothing here filters rows;
 *    it only orders them, most urgent first.
 *
 * The headline is three numbers side by side, never fused (§5): the grade
 * floor (worst critical claim), coverage at G2 or better, and the open
 * defeaters that make the claims defeasible.
 */

import type { Claim, ValidationCoverage, Verdict } from '@/lib/api'

const VERDICT: Record<Verdict, { label: string; cls: string; rank: number }> = {
  fails:            { label: 'fails',              cls: 'text-red-300 border-red-700 bg-red-900/20',          rank: 0 },
  not_assessed:     { label: 'not assessed',       cls: 'text-glow border-glow/60 bg-glow/10',                rank: 1 },
  holds_defeasible: { label: 'holds, defeasible',  cls: 'text-lavender border-lavender/50 bg-lavender/10',    rank: 2 },
  holds:            { label: 'holds',              cls: 'text-green-300 border-green-700 bg-green-900/20',    rank: 3 },
  not_applicable:   { label: 'not applicable',     cls: 'text-muted border-border bg-surface',                rank: 4 },
  out_of_scope:     { label: 'out of scope',       cls: 'text-muted border-border bg-surface',                rank: 5 },
}

export function orderClaims(claims: Claim[]): Claim[] {
  // Stable sort: within a verdict, the generator's own order is kept.
  return claims
    .map((c, i) => ({ c, i }))
    .sort((a, b) => (VERDICT[a.c.verdict].rank - VERDICT[b.c.verdict].rank) || (a.i - b.i))
    .map(({ c }) => c)
}

export default function ClaimsTable({ coverage }: { coverage: ValidationCoverage }) {
  const rows = orderClaims(coverage.claims)
  const failing = coverage.claims.filter(c => c.verdict === 'fails').length

  return (
    <section aria-label="Design claims">
      <h3 className="text-sm font-medium text-cream mb-3" style={{ fontFamily: 'EB Garamond, serif' }}>
        What this design is claimed to do
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4" data-testid="claims-headline">
        <Stat label="Grade floor" value={coverage.grade_floor ?? '—'}
              hint="worst grade among critical claims (G0 strongest, G7 asserted)" />
        <Stat label="Coverage ≤ G2" value={`${Math.round(coverage.coverage_le_g2 * 100)}%`}
              hint="share of critical claims with grade G2 or better" />
        <Stat label="Open defeaters" value={coverage.open_defeaters.join(', ') || 'none'}
              hint="recorded doubts: every claim citing one is defeasible" />
      </div>

      {failing > 0 && (
        <p className="text-sm text-red-300 mb-3">{failing} claim(s) fail — read those rows first.</p>
      )}
      {coverage.not_assessed.length > 0 && (
        <p className="text-sm text-glow mb-3">
          {coverage.not_assessed.length} check(s) were not assessed on this design. They are listed below,
          graded G7, because an unchecked rule is not a passed one.
        </p>
      )}

      <div className="overflow-x-auto border border-border rounded">
        <table className="w-full text-sm" data-testid="claims-table">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="font-normal px-3 py-2">Claim</th>
              <th className="font-normal px-3 py-2">Scope</th>
              <th className="font-normal px-3 py-2">Method</th>
              <th className="font-normal px-3 py-2">Grade</th>
              <th className="font-normal px-3 py-2">Defeaters</th>
              <th className="font-normal px-3 py-2">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(c => <Row key={c.id} claim={c} />)}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Row({ claim }: { claim: Claim }) {
  const v = VERDICT[claim.verdict]
  const quiet = claim.verdict === 'not_applicable' || claim.verdict === 'out_of_scope'
  return (
    <tr className={`border-b border-border/50 align-top ${quiet ? 'opacity-70' : ''}`}
        data-verdict={claim.verdict}>
      <td className="px-3 py-2">
        <p className="text-cream-dim leading-snug">{claim.claim}</p>
        {claim.detail && <p className="text-xs text-muted mt-0.5">{claim.detail}</p>}
        <p className="text-[10px] font-mono text-muted/70 mt-0.5">{claim.id}</p>
      </td>
      <td className="px-3 py-2 text-xs font-mono text-muted">
        {claim.scope ? `${claim.scope.parameters} · ${claim.scope.model}` : '—'}
      </td>
      <td className="px-3 py-2 text-xs font-mono text-muted">{claim.method ?? '—'}</td>
      <td className="px-3 py-2 text-xs font-mono text-cream">
        {claim.grade ?? '—'}
        {/* Stage 4: unsigned proofs and superseded claims are shown, but the
            floor does not look at them — say so where the grade is read. */}
        {!claim.critical && !quiet && claim.grade && (
          <span className="block text-[10px] text-muted whitespace-nowrap" title="not counted toward the grade floor">
            not counted
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-xs font-mono text-muted">
        {[...claim.defeaters].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1))).join(' ') || '—'}
      </td>
      <td className="px-3 py-2">
        <span className={`inline-block text-xs px-2 py-0.5 rounded border whitespace-nowrap ${v.cls}`}>
          {v.label}
        </span>
      </td>
    </tr>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="bg-surface border border-border rounded px-3 py-2" title={hint}>
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="text-lg font-mono text-cream mt-0.5 break-words">{value}</p>
    </div>
  )
}
