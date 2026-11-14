'use client'

import { BoardVerification as Report, BoardFinding } from '@/lib/api'
import { Section, VerdictBadge, type Tone } from '@/components/ui'

// The board verifier's report (backend/pcb_engine/verify.py), shown beside the
// board. Owner's decision 2026-10-17: a board whose checks fail stays on screen
// so it can be fixed; what is refused is its fabrication files. So this panel
// never hides the board — it says what was proven, what was only tested, what
// failed, and what nobody checked.

// What each rung means, said once so a pass on "evidence" never reads as proof.
const RUNG: Record<BoardFinding['rung'], string> = {
  exact: 'decided by arithmetic on the board',
  sound: 'an over-approximation: may fail a good board, never passes a bad one',
  bounded: 'checked up to a stated bound',
  evidence: 'a second source agrees; not a proof',
  unknown: 'not checked',
}

// A finding's status → verdict. A pass is a proof only on an exact or sound rung
// (that is what `proven` means in the report); a pass on a bounded or evidence
// rung holds with an open doubt. A check that was not run is grey and dashed.
function findingVerdict(f: BoardFinding): { tone: Tone; glyph: string; label: string } {
  if (f.status === 'fail') return { tone: 'fail', glyph: '✕', label: 'failed' }
  if (f.status === 'unknown') return { tone: 'none', glyph: '–', label: 'not checked' }
  if (f.rung === 'exact' || f.rung === 'sound') return { tone: 'pass', glyph: '✓', label: 'passed' }
  return { tone: 'warn', glyph: '~', label: 'passed, not proven' }
}

const ORDER: BoardFinding['status'][] = ['fail', 'unknown', 'pass']

export default function BoardVerification({ report }: { report: Report }) {
  const count = (s: BoardFinding['status']) => report.findings.filter(f => f.status === s).length
  const failed = count('fail'), unchecked = count('unknown'), passed = count('pass')
  const emit = report.gate?.emit ?? report.ok
  const rows = ORDER.flatMap(s => report.findings.filter(f => f.status === s))

  const overall: { tone: Tone; label: string } = !report.ok
    ? { tone: 'fail', label: 'a check failed' }
    : report.proven
      ? { tone: 'pass', label: 'proven on exact/sound checks' }
      : { tone: 'warn', label: 'no check failed · not proven' }

  return (
    <Section label="Independent board verifier" count={report.findings.length} id="board-verification">
      <div className="bv-summary">
        <VerdictBadge tone={overall.tone} label={overall.label} />
        <span className="t-data">
          <span className={failed ? 'c-fail' : 'c-fg-3'}>✕ {failed} failed</span>
          <span className="c-fg-3"> · </span>
          <span className={unchecked ? 'c-fg-2' : 'c-fg-3'}>– {unchecked} not checked</span>
          <span className="c-fg-3"> · </span>
          <span className={passed ? 'c-pass' : 'c-fg-3'}>✓ {passed} passed</span>
        </span>
        <span className="t-small">
          <span className="c-fg-3">Fab files </span>
          <span className={emit ? 'c-pass' : 'c-fail'}>{emit ? 'may be emitted' : 'would be refused'}</span>
        </span>
        <span className="t-small c-fg-3">not built or measured</span>
      </div>
      {report.gate?.reason && <p className="t-small c-fg-2 bv-reason">{report.gate.reason}</p>}

      <div className="dt-wrap">
        <table className="dt bv-table">
          <thead>
            <tr>
              <th style={{ width: 144 }}>Status</th>
              <th style={{ width: 72 }}>Check</th>
              <th>Finding</th>
              <th style={{ width: 96 }}>Rung</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f, i) => {
              const v = findingVerdict(f)
              return (
                <tr key={`${f.check}-${i}`} data-status={f.status}>
                  <td>
                    <VerdictBadge tone={v.tone} glyph={v.glyph} label={v.label} plain />
                  </td>
                  <td className="mono muted">{f.check}</td>
                  <td className="bv-finding">
                    <div>{f.claim}</div>
                    {f.detail && <div className="t-small c-fg-2 bv-detail">{f.detail}</div>}
                  </td>
                  <td>
                    <span className={`chip chip-mono ${f.rung === 'unknown' ? 'chip-none' : ''}`} title={RUNG[f.rung]}>
                      {f.rung}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <style>{CSS}</style>
    </Section>
  )
}

const CSS = `
.bv-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; margin-bottom: 8px; }
.bv-reason { margin-bottom: 8px; max-width: 78ch; }
.bv-table { min-width: 600px; }
.bv-finding { padding-top: 6px; padding-bottom: 6px; }
.bv-detail { margin-top: 2px; overflow-wrap: anywhere; max-width: 78ch; }
`
