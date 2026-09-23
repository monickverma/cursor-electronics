'use client'

import ClaimsTable from '@/components/ClaimsTable'
import type { ValidationCoverage } from '@/lib/api'

interface ValidationData {
  passed: boolean
  errors: Array<{ field: string; message: string }>
  warnings: Array<{ field: string; message: string }>
}

interface Props {
  validation: ValidationData
  explanation?: string
  // Stage 3 claim objects. Absent on designs built before Stage 3.
  coverage?: ValidationCoverage | null
}

export default function ValidationReport({ validation, explanation, coverage }: Props) {
  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {coverage && <ClaimsTable coverage={coverage} />}

      {/* Overall badge. With claim objects present it must not say "all rules
          passed" while rules sit unassessed — that is the silent pass X8 ends. */}
      <div className={`inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm border ${
        !validation.passed
          ? 'bg-red-900/20 border-red-700 text-red-400'
          : coverage && coverage.not_assessed.length > 0
            ? 'bg-glow/10 border-glow/60 text-glow'
            : 'bg-green-900/20 border-green-700 text-green-400'
      }`}>
        {!validation.passed
          ? `✗ ${validation.errors.length} error(s)`
          : coverage
            ? coverage.not_assessed.length > 0
              ? `No rule errors — ${coverage.not_assessed.length} check(s) not assessed`
              : '✓ No rule errors; every check assessed or accounted for'
            : '✓ All rules passed'}
      </div>

      {/* Errors */}
      {validation.errors.length > 0 && (
        <Section title="Errors" count={validation.errors.length} variant="error">
          {validation.errors.map((e, i) => (
            <RuleRow key={i} field={e.field} message={e.message} variant="error" />
          ))}
        </Section>
      )}

      {/* Warnings */}
      {validation.warnings.length > 0 && (
        <Section title="Warnings" count={validation.warnings.length} variant="warning">
          {validation.warnings.map((w, i) => (
            <RuleRow key={i} field={w.field} message={w.message} variant="warning" />
          ))}
        </Section>
      )}

      {/* Design explanation */}
      {explanation && (
        <section>
          <h3 className="text-sm font-medium text-cream mb-3" style={{ fontFamily: 'EB Garamond, serif' }}>
            Design Explanation
          </h3>
          <div className="text-sm text-cream-dim leading-relaxed whitespace-pre-wrap bg-surface border border-border rounded p-4">
            {explanation}
          </div>
        </section>
      )}

      {validation.errors.length === 0 && validation.warnings.length === 0 && !explanation && !coverage && (
        <p className="text-sm text-muted">No issues found.</p>
      )}
    </div>
  )
}

function Section({ title, count, variant, children }: {
  title: string
  count: number
  variant: 'error' | 'warning'
  children: React.ReactNode
}) {
  const color = variant === 'error' ? 'text-red-400' : 'text-amber-400'
  return (
    <section>
      <h3 className={`text-sm font-medium mb-2 ${color}`}>
        {title} <span className="opacity-60">({count})</span>
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  )
}

function RuleRow({ field, message, variant }: {
  field: string
  message: string
  variant: 'error' | 'warning'
}) {
  const borderColor = variant === 'error' ? 'border-red-800' : 'border-amber-800'
  const bg = variant === 'error' ? 'bg-red-900/10' : 'bg-amber-900/10'
  return (
    <div className={`rounded border ${borderColor} ${bg} px-3 py-2`}>
      <p className="text-xs font-mono text-muted mb-0.5">{field}</p>
      <p className="text-sm text-cream-dim leading-snug">{message}</p>
    </div>
  )
}
