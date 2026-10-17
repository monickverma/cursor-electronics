'use client'

import { BoardVerification as Report, BoardFinding } from '@/lib/api'

// The board verifier's report (backend/pcb_engine/verify.py), shown beside the
// board. Owner's decision 2026-10-17: a board whose checks fail stays on screen
// so it can be fixed; what is refused is its fabrication files. So this panel
// never hides the board — it says what was proven, what was only tested, what
// failed, and what nobody checked.

const STATUS: Record<BoardFinding['status'], { mark: string; color: string; label: string }> = {
  fail: { mark: '✕', color: '#f87171', label: 'Failed' },
  unknown: { mark: '?', color: '#fbbf24', label: 'Not checked' },
  pass: { mark: '✓', color: '#4ade80', label: 'Passed' },
}

// What each rung means, said once so a pass on "evidence" never reads as proof.
const RUNG: Record<BoardFinding['rung'], string> = {
  exact: 'decided by arithmetic on the board',
  sound: 'an over-approximation: may fail a good board, never passes a bad one',
  bounded: 'checked up to a stated bound',
  evidence: 'a second source agrees; not a proof',
  unknown: 'not checked',
}

const ORDER: BoardFinding['status'][] = ['fail', 'unknown', 'pass']

export default function BoardVerification({ report }: { report: Report }) {
  const counts = ORDER.map(s => [s, report.findings.filter(f => f.status === s).length] as const)
  const emit = report.gate?.emit ?? report.ok

  return (
    <details open={!report.ok} className="border-t border-border-dark" style={{ background: '#141414' }}>
      <summary
        className="px-4 py-2 text-xs cursor-pointer select-none flex flex-wrap gap-x-4 gap-y-1"
        style={{ color: 'var(--lumen-dim)' }}
      >
        <span style={{ color: 'var(--lumen)' }}>Board verification</span>
        {counts.map(([s, n]) => (
          <span key={s} style={{ color: n ? STATUS[s].color : 'var(--text-muted-dark)' }}>
            {STATUS[s].mark} {n} {STATUS[s].label.toLowerCase()}
          </span>
        ))}
        <span style={{ color: emit ? '#4ade80' : '#f87171' }}>
          Fab files: {emit ? 'may be emitted' : 'would be refused'}
        </span>
        <span style={{ color: 'var(--text-muted-dark)' }}>
          {report.proven ? 'proven on exact/sound checks' : 'not proven'}
          {' · '}not built or measured
        </span>
      </summary>

      <div className="px-4 pb-3 max-h-64 overflow-auto">
        {report.gate?.reason && (
          <p className="text-xs mb-2" style={{ color: 'var(--text-muted-dark)' }}>
            {report.gate.reason}
          </p>
        )}
        <ul className="space-y-1.5">
          {ORDER.flatMap(s => report.findings.filter(f => f.status === s)).map((f, i) => (
            <li key={`${f.check}-${i}`} className="text-xs leading-relaxed">
              <div className="flex gap-2 items-baseline">
                <span style={{ color: STATUS[f.status].color, minWidth: 12 }} aria-label={STATUS[f.status].label}>
                  {STATUS[f.status].mark}
                </span>
                <span className="font-mono" style={{ color: 'var(--text-muted-dark)', minWidth: 44 }}>
                  {f.check}
                </span>
                <span style={{ color: 'var(--lumen)' }}>{f.claim}</span>
                <span
                  className="font-mono shrink-0"
                  title={RUNG[f.rung]}
                  style={{ color: 'var(--text-muted-dark)', border: '1px solid var(--border-dark)', borderRadius: 4, padding: '0 4px' }}
                >
                  {f.rung}
                </span>
              </div>
              {f.detail && (
                <p className="ml-14" style={{ color: 'var(--lumen-dim)', overflowWrap: 'anywhere' }}>
                  {f.detail}
                </p>
              )}
            </li>
          ))}
        </ul>
      </div>
    </details>
  )
}
