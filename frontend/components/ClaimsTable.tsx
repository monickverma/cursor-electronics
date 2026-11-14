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

import { Fragment } from 'react'
import type { Claim, ValidationCoverage, Verdict } from '@/lib/api'
import { Callout, Chip, GradeChip, VerdictBadge, VERDICTS } from '@/components/ui'

const RANK: Record<Verdict, number> = {
  fails: 0, not_assessed: 1, holds_defeasible: 2, holds: 3, not_applicable: 4, out_of_scope: 5,
}
const ORDER: Verdict[] = ['fails', 'not_assessed', 'holds_defeasible', 'holds', 'not_applicable', 'out_of_scope']
const COUNT_TONE: Record<Verdict, string> = {
  holds: 'c-pass', holds_defeasible: 'c-warn', fails: 'c-fail',
  not_assessed: 'c-none', out_of_scope: 'c-none', not_applicable: 'c-none',
}

// Under 640px each row stacks: verdict and grade on one line, then the claim, method, scope and
// defeaters full width. Still a <table> with tbody rows (the e2e suite reads it as one).
export const STACK = [
  'max-sm:block max-sm:min-w-0 max-sm:[&_thead]:hidden max-sm:[&_tbody]:block',
  'max-sm:[&_tr]:grid max-sm:[&_tr]:grid-cols-[auto_minmax(0,1fr)] max-sm:[&_tr]:gap-x-2 max-sm:[&_tr]:gap-y-1.5',
  'max-sm:[&_tr]:py-3 max-sm:[&_tr]:border-b max-sm:[&_tr]:border-line',
  'max-sm:[&_td]:block max-sm:[&_td]:!p-0 max-sm:[&_td]:!h-auto max-sm:[&_td]:!border-0',
  'max-sm:[&_td:nth-child(n+3)]:col-span-2',
].join(' ')

export function orderClaims(claims: Claim[]): Claim[] {
  // Stable sort: within a verdict, the generator's own order is kept.
  return claims
    .map((c, i) => ({ c, i }))
    .sort((a, b) => (RANK[a.c.verdict] - RANK[b.c.verdict]) || (a.i - b.i))
    .map(({ c }) => c)
}

export default function ClaimsTable({ coverage }: { coverage: ValidationCoverage }) {
  const rows = orderClaims(coverage.claims)
  const failing = coverage.claims.filter(c => c.verdict === 'fails').length
  const counts = ORDER.map(v => [v, coverage.claims.filter(c => c.verdict === v).length] as const)

  return (
    <div aria-label="Design claims" role="region">
      <div data-testid="claims-headline">
        <div className="rule-grid grid-cols-3">
          <Stat label="Grade floor" hint="worst grade among critical claims (G0 strongest, G7 asserted)">
            {coverage.grade_floor ?? <span className="text-fg-3">none</span>}
          </Stat>
          <Stat label="Coverage ≤ G2" hint="share of critical claims with grade G2 or better">
            {`${Math.round(coverage.coverage_le_g2 * 100)}%`}
          </Stat>
          <Stat label="Open defeaters" hint="recorded doubts: every claim citing one is defeasible">
            {coverage.open_defeaters.join(', ') || <span className="text-fg-3">none</span>}
          </Stat>
        </div>
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 t-small">
          {counts.filter(([v, n]) => n > 0 || v === 'fails').map(([v, n]) => {
            const m = VERDICTS[v]
            return (
              <span key={v} className={`inline-flex items-baseline gap-1.5 ${n === 0 ? 'text-fg-3' : COUNT_TONE[v]}`}>
                <span className="font-mono font-semibold" aria-hidden="true">{m.glyph}</span>
                <span className="font-mono">{n}</span>
                <span>{m.word}</span>
              </span>
            )
          })}
        </p>
      </div>

      {(failing > 0 || coverage.not_assessed.length > 0) && (
        <div className="mt-4 flex flex-col gap-2">
          {failing > 0 && (
            <Callout tone="fail">{failing} claim(s) fail — read those rows first.</Callout>
          )}
          {coverage.not_assessed.length > 0 && (
            <Callout>
              {coverage.not_assessed.length} check(s) were not assessed on this design. They are listed below,
              graded G7, because an unchecked rule is not a passed one.
            </Callout>
          )}
        </div>
      )}

      <div className="dt-wrap mt-4">
        <table className={`dt table-fixed min-w-[920px] ${STACK}`} data-testid="claims-table">
          <colgroup>
            <col className="w-[156px]" />
            <col className="w-[88px]" />
            <col />
            <col className="w-[168px]" />
            <col className="w-[192px]" />
            <col className="w-[116px]" />
          </colgroup>
          <thead>
            <tr>
              <th>Verdict</th>
              <th>Grade</th>
              <th>Claim</th>
              <th>Kind · method</th>
              <th>Scope</th>
              <th>Defeaters</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(c => <Row key={c.id} claim={c} />)}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Row({ claim }: { claim: Claim }) {
  const quiet = claim.verdict === 'not_applicable' || claim.verdict === 'out_of_scope' || claim.verdict === 'not_assessed'
  const defeaters = [...claim.defeaters].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)))
  return (
    <tr data-verdict={claim.verdict} className="[&>td]:!align-top">
      <td className="!py-2">
        <VerdictBadge verdict={claim.verdict} />
      </td>
      <td className="!py-2">
        <GradeChip grade={claim.grade} />
        {/* Stage 4: unsigned proofs and superseded claims are shown, but the
            floor does not look at them — say so where the grade is read. */}
        {!claim.critical && !quiet && claim.grade && (
          <span className="block mt-1 t-small text-fg-3 whitespace-nowrap" title="not counted toward the grade floor">
            not counted
          </span>
        )}
      </td>
      <td className="!py-2">
        <p className={`t-ui ${quiet ? 'text-fg-2' : 'text-fg'}`}>{claim.claim}</p>
        {claim.detail && <p className="t-small text-fg-2 mt-0.5">{claim.detail}</p>}
        <p className="mt-1 flex flex-wrap items-center gap-2">
          {claim.critical && <Chip label title="counted toward the grade floor">Critical</Chip>}
          <span className="t-data text-fg-3 break-all">{claim.id}</span>
        </p>
      </td>
      <td className="!py-2 mono muted">
        <span className="break-words">{claim.kind}{claim.method ? <> · {claim.method}</> : null}</span>
      </td>
      <td className={`!py-2 mono ${claim.scope ? '' : 'max-sm:!hidden'}`}>
        {claim.scope ? (
          <>
            <span className="block text-fg-2">{claim.scope.parameters}</span>
            <span className="block text-fg-3 break-words">
              {claim.scope.model.split('+').map((part, i) => (
                <Fragment key={i}>{i > 0 && <>+<wbr /></>}{part}</Fragment>
              ))}
            </span>
          </>
        ) : <span className="text-fg-3">–</span>}
      </td>
      <td className={`!py-2 ${defeaters.length > 0 ? '' : 'max-sm:!hidden'}`}>
        {defeaters.length > 0
          ? <span className="flex flex-wrap gap-1">{defeaters.map(d => <Chip key={d} mono>{d}</Chip>)}</span>
          : <span className="text-fg-3">–</span>}
      </td>
    </tr>
  )
}

function Stat({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3 flex flex-col gap-2" title={hint}>
      <p className="t-label">{label}</p>
      <p className="font-mono text-[16px] sm:text-[20px] leading-none text-fg break-words">{children}</p>
    </div>
  )
}
