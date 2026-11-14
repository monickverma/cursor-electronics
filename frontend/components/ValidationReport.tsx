'use client'

/**
 * Sheet 06 — Validation: the rules, every claim with its own grade, and the
 * properties proved over component tolerances with their sign-off.
 * The explanation and the blocks table live on the Overview sheet.
 */

import ClaimsTable, { STACK } from '@/components/ClaimsTable'
import PropertiesPanel from '@/components/PropertiesPanel'
import type { ValidationCoverage } from '@/lib/api'
import { Chip, EmptyState, Section, SheetFrame, VerdictBadge } from '@/components/ui'

interface ValidationData {
  passed: boolean
  errors: Array<{ field: string; message: string }>
  warnings: Array<{ field: string; message: string }>
}

interface Props {
  validation: ValidationData
  // Kept for the caller; the explanation is shown on the Overview sheet.
  explanation?: string
  explanationError?: string | null
  explanationStatus?: string
  // Stage 3 claim objects. Absent on designs built before Stage 3.
  coverage?: ValidationCoverage | null
  // Stage 4 sign-off needs the design and the session.
  circuitId?: string
  token?: string
  onCoverage?: (coverage: ValidationCoverage) => void
}

export default function ValidationReport({ validation, coverage, circuitId, token, onCoverage }: Props) {
  const properties = coverage?.properties ?? []
  const nErr = validation.errors.length
  const nWarn = validation.warnings.length

  const meta = (
    <span className="t-data">
      {coverage && <>grade floor {coverage.grade_floor ?? 'none'} · {coverage.claims.length} claims · </>}
      {properties.length > 0 && <>{properties.length} properties, {coverage?.properties_signed ? 'signed' : 'not signed'} · </>}
      {nErr} error{nErr === 1 ? '' : 's'} · {nWarn} warning{nWarn === 1 ? '' : 's'}
    </span>
  )

  return (
    <SheetFrame meta={meta}>
      <div className="max-w-[1240px]">
        <Section label="Rules" count={nErr + nWarn}>
          {nErr === 0 && nWarn === 0 ? (
            <p className="text-fg-2 flex items-baseline gap-2">
              <VerdictBadge tone="pass" label="passed" plain />
              {/* With claim objects present this must not say "all rules passed"
                  while rules sit unassessed — that is the silent pass X8 ends. */}
              <span>
                {coverage
                  ? coverage.not_assessed.length > 0
                    ? `No rule errors or warnings — ${coverage.not_assessed.length} check(s) not assessed; see the claims below.`
                    : 'No rule errors or warnings; every check assessed or accounted for.'
                  : 'All rules passed.'}
              </span>
            </p>
          ) : (
            <table className={`dt ${STACK}`}>
              <thead>
                <tr><th className="w-[120px]">Severity</th><th className="w-[200px]">Field</th><th>Message</th></tr>
              </thead>
              <tbody>
                {validation.errors.map((e, i) => (
                  <RuleRow key={`e${i}`} field={e.field} message={e.message} error />
                ))}
                {validation.warnings.map((w, i) => (
                  <RuleRow key={`w${i}`} field={w.field} message={w.message} />
                ))}
              </tbody>
            </table>
          )}
        </Section>

        <Section label="Claims" count={coverage ? coverage.claims.length : undefined}>
          {coverage
            ? <ClaimsTable coverage={coverage} />
            : <EmptyState title="No claims on this design">It was built before claim objects existed; regenerate it to grade each claim.</EmptyState>}
        </Section>

        {coverage && properties.length > 0 && (
          <Section
            label="Proved properties"
            count={properties.length}
            actions={coverage.properties_signed
              ? <VerdictBadge tone="pass" label="signed" />
              : <Chip>not signed</Chip>}
          >
            {/* Keyed on the set and its standing, so a message about one property
                set never lingers over another. */}
            <PropertiesPanel key={`${coverage.properties_hash ?? ''}:${!!coverage.properties_signed}`}
                             coverage={coverage} circuitId={circuitId} token={token} onSigned={onCoverage} />
          </Section>
        )}
      </div>
    </SheetFrame>
  )
}

function RuleRow({ field, message, error = false }: { field: string; message: string; error?: boolean }) {
  return (
    <tr className="[&>td]:!align-top">
      <td className="!py-2">
        <VerdictBadge tone={error ? 'fail' : 'warn'} label={error ? 'error' : 'warning'} glyph={error ? '✕' : '~'} />
      </td>
      <td className="!py-2 mono muted break-all">{field}</td>
      <td className="!py-2 t-ui">{message}</td>
    </tr>
  )
}
