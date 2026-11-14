'use client'

/**
 * The properties a design is proved against, and the sign-off. Stage 4.
 *
 * Each sentence is generated from the formula the prover decided, by template,
 * so the words a person agrees to are exactly what was proved. Until the set
 * is signed the proofs are shown and do not count toward the grade floor.
 * Signing quotes the hash of the sentences on screen: if the design moved
 * underneath them, the backend answers 409 and nothing is signed.
 *
 * A sentence that begins with a `[tag]` (a composed board's block) is grouped
 * under that tag. The tag is drawn as a chip, and its text stays in the DOM
 * (read by screen readers) so the sentence a person signs is still whole.
 */

import { useState } from 'react'
import { signOffDesign, type PropertyView, type ValidationCoverage } from '@/lib/api'
import {
  Button, Callout, Chip, CopyButton, GradeChip, KeyValue, KeyValueList, VerdictBadge, propertyTone,
} from '@/components/ui'

const STATUS_WORD: Record<PropertyView['status'], string> = {
  proven: 'proven',
  refuted: 'refuted',
  unknown: 'undecided',
}

const TAG = /^\[([^\]]+)\]\s*/

function splitTag(sentence: string): { tag: string | null; prefix: string; rest: string } {
  const m = sentence.match(TAG)
  return m ? { tag: m[1], prefix: m[0], rest: sentence.slice(m[0].length) } : { tag: null, prefix: '', rest: sentence }
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

  // Groups in order of first appearance; untagged sentences form one unlabelled group.
  const groups: Array<{ tag: string | null; items: PropertyView[] }> = []
  for (const p of properties) {
    const { tag } = splitTag(p.english)
    const g = groups.find(x => x.tag === tag)
    if (g) g.items.push(p)
    else groups.push({ tag, items: [p] })
  }
  const labelled = groups.some(g => g.tag !== null)

  return (
    <div aria-label="Proved properties" role="region" data-testid="properties-panel">
      {groups.map((g, gi) => (
        <div key={g.tag ?? '_'} className={gi > 0 ? 'mt-6' : undefined}>
          {labelled && g.tag !== null && (
            <h4 className="flex items-center gap-2 h-7 border-b border-line-2">
              <span className="t-label text-fg-2">{g.tag}</span>
              <span className="section-count">{g.items.length}</span>
            </h4>
          )}
          <ol>
            {g.items.map(p => <PropertyRow key={p.id} p={p} />)}
          </ol>
        </div>
      ))}

      <div className="mt-6 border border-line-2 bg-bench-2">
        <div className="flex items-center gap-2 h-8 px-4 border-b border-line">
          <span className="t-label">Sign-off</span>
          <span className="ml-auto">
            {signed && <VerdictBadge tone="pass" label="signed" />}
          </span>
        </div>
        <div className="px-4 py-4 flex flex-col gap-3">
          <p className="text-fg-2 max-w-[78ch]">
            {signed
              ? `Signed off by ${coverage.signed_by}. These proofs count toward the grade floor and are frozen: changing one means changing the requirement and signing again.`
              : 'Read each sentence. Proofs are shown, but count only once you sign that these are the properties you want.'}
          </p>
          {coverage.properties_hash && (
            <div className="flex items-center gap-2 min-w-0">
              <p className="min-w-0">
                <span className="t-label mr-2">Property set{' '}</span>
                <code className="t-data text-fg break-all">{coverage.properties_hash}</code>
              </p>
              <CopyButton value={coverage.properties_hash} label="property set hash" className="flex-none" />
            </div>
          )}
          {!signed && (
            <div>
              <Button variant="primary" onClick={sign} disabled={!canSign || busy}>
                {busy ? 'Signing…' : `Sign off these ${properties.length} properties`}
              </Button>
            </div>
          )}
          {error && (
            <Callout tone="fail" title="Nothing was signed" role="alert">
              <span className="whitespace-pre-wrap">{error}</span>
            </Callout>
          )}
        </div>
      </div>
    </div>
  )
}

function PropertyRow({ p }: { p: PropertyView }) {
  const { tag, prefix, rest } = splitTag(p.english)
  return (
    <li className="grid gap-x-6 gap-y-2 py-3 border-b border-line sm:grid-cols-[184px_minmax(0,1fr)]" data-status={p.status}>
      <div className="flex flex-wrap items-center content-start gap-1.5 min-w-0">
        <VerdictBadge tone={propertyTone(p.status)} label={STATUS_WORD[p.status]} />
        <GradeChip grade={p.grade} />
        <span className="w-full t-data text-fg-2 break-all">{p.id}</span>
      </div>
      <div className="min-w-0">
        <p className="t-ui !leading-[1.55] text-fg max-w-[78ch]">
          {tag && <Chip mono aria-hidden="true" className="mr-2 align-[1px]">{tag}</Chip>}
          {tag && <span className="sr-only">{prefix}</span>}
          {rest}
        </p>
        <p className="t-data text-fg-3 mt-1.5 break-words">
          {p.method}{p.re_derives ? ` · re-derives ${p.re_derives}` : ''}
        </p>
        {p.counterexample && (
          <Callout tone="fail" title="Counterexample" className="mt-2 max-w-[440px]">
            <KeyValueList>
              {Object.entries(p.counterexample).map(([k, v]) => (
                <KeyValue key={k} label={<span className="normal-case tracking-normal font-mono font-normal">{k}</span>} value={v} />
              ))}
            </KeyValueList>
          </Callout>
        )}
      </div>
    </li>
  )
}
