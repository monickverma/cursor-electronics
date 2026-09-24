'use client'

/**
 * The properties a design is proved against, and the sign-off. Stage 4.
 *
 * Each sentence is generated from the formula the prover decided, by template,
 * so the words a person agrees to are exactly what was proved. Until the set
 * is signed the proofs are shown and do not count toward the grade floor.
 * Signing quotes the hash of the sentences on screen: if the design moved
 * underneath them, the backend answers 409 and nothing is signed.
 */

import { useState } from 'react'
import { signOffDesign, type PropertyView, type ValidationCoverage } from '@/lib/api'

const STATUS: Record<PropertyView['status'], { label: string; cls: string }> = {
  proven:  { label: 'proven',  cls: 'text-green-300 border-green-700 bg-green-900/20' },
  refuted: { label: 'refuted', cls: 'text-red-300 border-red-700 bg-red-900/20' },
  unknown: { label: 'undecided', cls: 'text-glow border-glow/60 bg-glow/10' },
}

interface Props {
  coverage: ValidationCoverage
  circuitId?: string
  token?: string
  onSigned?: (coverage: ValidationCoverage) => void
}

export default function PropertiesPanel({ coverage, circuitId, token, onSigned }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const properties = coverage.properties ?? []
  if (properties.length === 0) return null

  const signed = !!coverage.properties_signed
  const canSign = !signed && !!circuitId && !!token && !!coverage.properties_hash

  async function sign() {
    if (!canSign) return
    setBusy(true)
    setError(null)
    try {
      const res = await signOffDesign(circuitId!, coverage.properties_hash!, token!)
      onSigned?.(res.validation_coverage)
    } catch (e) {
      // fetch() rejects with a TypeError when the server cannot be reached;
      // the backend's own refusals arrive as Errors carrying its message.
      setError(e instanceof TypeError
        ? 'Could not reach the server. Nothing was signed.'
        : e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Proved properties" data-testid="properties-panel">
      <h3 className="text-sm font-medium text-cream mb-1" style={{ fontFamily: 'EB Garamond, serif' }}>
        What is proved about this design
      </h3>
      <p className="text-xs text-muted mb-3">
        {signed
          ? `Signed off by ${coverage.signed_by}. These proofs count toward the grade floor and are frozen: changing one means changing the requirement and signing again.`
          : 'Read each sentence. Proofs are shown, but count only once you sign that these are the properties you want.'}
      </p>

      <ol className="space-y-2 mb-3">
        {properties.map(p => {
          const s = STATUS[p.status]
          return (
            <li key={p.id} className="bg-surface border border-border rounded px-3 py-2" data-status={p.status}>
              <div className="flex flex-col sm:flex-row sm:items-start gap-2">
                <p className="text-sm text-cream-dim leading-snug flex-1">{p.english}</p>
                <span className={`self-start text-xs px-2 py-0.5 rounded border whitespace-nowrap ${s.cls}`}>
                  {s.label}{p.grade ? ` · ${p.grade}` : ''}
                </span>
              </div>
              {p.counterexample && (
                <p className="text-xs text-red-300 mt-1 font-mono break-words">
                  counterexample: {Object.entries(p.counterexample).map(([k, v]) => `${k}=${v}`).join(', ')}
                </p>
              )}
              <p className="text-[10px] font-mono text-muted/70 mt-1">
                {p.id} · {p.method}{p.re_derives ? ` · re-derives ${p.re_derives}` : ''}
              </p>
            </li>
          )
        })}
      </ol>

      <div className="flex flex-col sm:flex-row sm:items-center gap-2">
        {!signed && (
          <button
            type="button"
            onClick={sign}
            disabled={!canSign || busy}
            className="bg-lavender text-dark hover:bg-lavender-dim disabled:opacity-50 rounded px-3 py-1.5 text-sm"
          >
            {busy ? 'Signing…' : `Sign off these ${properties.length} properties`}
          </button>
        )}
        <p className="text-[10px] font-mono text-muted break-all">
          set {coverage.properties_hash?.slice(0, 16)}
        </p>
      </div>
      {error && <p className="text-sm text-red-300 mt-2 whitespace-pre-wrap">{error}</p>}
    </section>
  )
}
