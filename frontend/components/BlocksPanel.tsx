'use client'

/**
 * A composed board's blocks and behaviour (Composition M4). Each block was
 * built and proved by its own generator; this lists where each one sits on
 * the board, the parts it placed, and the rules the firmware runs. Rendered
 * only for a project — a single design has no `blocks`.
 */

import type { ValidationCoverage } from '@/lib/api'

export default function BlocksPanel({ coverage }: { coverage: ValidationCoverage }) {
  const blocks = coverage.blocks ?? []
  if (blocks.length === 0) return null
  const behaviour = coverage.behaviour ?? []

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-medium text-cream mb-1" style={{ fontFamily: 'EB Garamond, serif' }}>
        Blocks on this board
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted">
            <th className="py-1 pr-3 font-normal">Block</th>
            <th className="py-1 pr-3 font-normal">Circuit</th>
            <th className="py-1 pr-3 font-normal">Pin</th>
            <th className="py-1 font-normal">Parts</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map(b => (
            <tr key={b.id} className="border-b border-border/50">
              <td className="py-1 pr-3 font-mono text-lavender">{b.id}</td>
              <td className="py-1 pr-3 text-cream">
                {b.function}
                <span className="block text-[10px] font-mono text-muted/70">{b.generator}</span>
              </td>
              <td className="py-1 pr-3 font-mono text-cream">{b.pin}</td>
              <td className="py-1 font-mono text-muted">{b.parts.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <p className="text-xs text-muted mb-1">Behaviour the firmware runs (later rules win)</p>
        {behaviour.length === 0
          ? <p className="text-sm text-muted">None: every output stays off.</p>
          : (
            <ol className="list-decimal list-inside text-sm text-cream space-y-0.5">
              {behaviour.map((rule, i) => <li key={i} className="font-mono text-xs">{rule}</li>)}
            </ol>
          )}
      </div>
    </section>
  )
}
