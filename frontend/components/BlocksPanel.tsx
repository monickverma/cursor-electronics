'use client'

/**
 * A composed board's blocks and behaviour (Composition M4). Each block was
 * built and proved by its own generator; this lists where each one sits on
 * the board, the parts it placed, and the rules the firmware runs. Rendered
 * only for a project — a single design has no `blocks`.
 *
 * No heading of its own: the caller's Section is the heading.
 */

import type { ValidationCoverage } from '@/lib/api'

export default function BlocksPanel({ coverage }: { coverage: ValidationCoverage }) {
  const blocks = coverage.blocks ?? []
  if (blocks.length === 0) return null
  const behaviour = coverage.behaviour ?? []

  return (
    <div className="flex flex-col gap-[24px]">
      <div className="dt-wrap">
        <table className="dt">
          <thead>
            <tr>
              <th scope="col">Block</th>
              <th scope="col">Function · generator</th>
              <th scope="col">Pin</th>
              <th scope="col">Parts</th>
            </tr>
          </thead>
          <tbody>
            {blocks.map(b => (
              <tr key={b.id}>
                <td className="mono">{b.id}</td>
                <td>
                  <span className="block">{b.function}</span>
                  <span className="block t-data c-fg-3" style={{ fontSize: 11 }}>{b.generator}</span>
                </td>
                <td className="mono">{b.pin}</td>
                <td className="mono c-fg-2">{b.parts.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <p className="t-label mb-[8px]">Behaviour the firmware runs · later rules win</p>
        {behaviour.length === 0
          ? <p className="t-small c-fg-2">None: every output stays off.</p>
          : (
            <ol className="border-t border-line">
              {behaviour.map((rule, i) => (
                <li key={i} className="flex gap-[12px] border-b border-line py-[6px]">
                  <span className="t-data c-fg-3 flex-none">{String(i + 1).padStart(2, '0')}</span>
                  <span className="t-data c-fg" style={{ overflowWrap: 'anywhere' }}>{rule}</span>
                </li>
              ))}
            </ol>
          )}
      </div>
    </div>
  )
}
