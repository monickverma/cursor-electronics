'use client'

/**
 * Status bar — the drawing's title block, 26px of mono cells. Only facts on the response:
 * a cell the response has no data for is omitted (never shown as zero or a dash).
 * Under 720px only RULES, GRADE FLOOR and the mode remain (cells marked `sb-opt` hide).
 */
import { Cursor, firmwareTone } from '@/components/ui'
import { claimCounts, claimCountsTitle, type DesignFacts } from './facts'

export function StatusBar({ facts, demo }: { facts: DesignFacts | null; demo: boolean }) {
  const v = facts?.validation
  const cov = facts?.coverage ?? null
  const counts = cov ? claimCounts(cov) : null
  const fw = facts?.firmwareBuild ?? null
  const fwTone = fw ? firmwareTone(fw.status) : null

  return (
    <footer className="sb" aria-label="Title block">
      {facts && (
        <span className="sb-cell sb-opt" title={facts.circuitId}>
          <span className="sb-k">Design</span>
          <span className="sb-v">{facts.circuitId.slice(0, 8)}</span>
        </span>
      )}
      {facts?.version !== undefined && (
        <span className="sb-cell sb-opt">
          <span className="sb-k">Rev</span>
          <span className="sb-v">v{facts.version}</span>
        </span>
      )}
      {v && (
        <span className="sb-cell" title={v.passed ? 'The rule engine passed this design' : 'The rule engine found errors'}>
          <span className="sb-k">Rules</span>
          <span className={v.passed ? 'c-pass' : 'c-fail'} aria-hidden="true">{v.passed ? '✓' : '✕'}</span>
          <span className={v.errors.length > 0 ? 'c-fail' : 'sb-v'}>
            {v.errors.length} {v.errors.length === 1 ? 'error' : 'errors'}
          </span>
          <span className="c-fg-3">·</span>
          <span className="sb-v">{v.warnings.length} {v.warnings.length === 1 ? 'warning' : 'warnings'}</span>
        </span>
      )}
      {counts && (
        <span className="sb-cell sb-opt" title={claimCountsTitle(counts)}>
          <span className="sb-k">Claims</span>
          <span className="c-pass">{counts.holds} ✓</span>
          <span className="c-warn">{counts.defeasible} ~</span>
          <span className="c-fail">{counts.fails} ✕</span>
          <span className="c-none">{counts.open} –</span>
          <span className="sr-only">{claimCountsTitle(counts)}</span>
        </span>
      )}
      {cov?.grade_floor && (
        <span className="sb-cell" title="The weakest grade among the critical, graded claims">
          <span className="sb-k">Grade floor</span>
          <span className="sb-v">{cov.grade_floor}</span>
        </span>
      )}
      {fw && fw.status !== 'none' && (
        <span className="sb-cell sb-opt" title={fw.message || undefined}>
          <span className="sb-k">Firmware</span>
          <span className={fwTone && fwTone !== 'neutral' ? `c-${fwTone}` : 'sb-v'}>{fw.status}</span>
          {fw.status === 'compiling' && <Cursor />}
        </span>
      )}
      <span className="sb-fill" />
      <span className="sb-cell sb-mode" title={demo ? 'Recorded results — no backend is attached' : 'Connected to the live backend'}>
        <span className={demo ? 'c-warn' : 'sb-v'}>{demo ? 'DEMO' : 'LIVE'}</span>
      </span>
    </footer>
  )
}
