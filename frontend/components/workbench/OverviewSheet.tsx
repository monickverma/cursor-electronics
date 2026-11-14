'use client'

/**
 * Sheet 00 — Overview: the compile report, built only from fields on the response.
 *  1. the intent and the design's identity;
 *  2. the verdict strip (claims counted by verdict, grade floor, open defeaters, properties) —
 *     or "No claims on this design" when the response has no coverage, never a row of zeros;
 *  3. the pipeline: one cell per stage, each a button that opens its sheet;
 *  4. blocks and behaviour (BlocksPanel), 5. why this design (ExplanationPanel, which polls).
 */
import type { ReactNode } from 'react'
import { ArrowRight } from 'lucide-react'
import BlocksPanel from '@/components/BlocksPanel'
import ExplanationPanel from '@/components/ExplanationPanel'
import type { GenerateResponse } from '@/lib/api'
import {
  Chip, CopyButton, Cursor, GradeChip, Section, SheetFrame, firmwareTone,
  type ToneOrNeutral,
} from '@/components/ui'
import { claimCounts, claimCountsTitle, designFacts, type DesignResult } from './facts'
import { SHEET_BY_ID, type SheetId } from './sheets'

interface Props {
  result: DesignResult
  token: string
  onOpenSheet: (id: SheetId) => void
}

export function OverviewSheet({ result, token, onOpenSheet }: Props) {
  const f = designFacts(result)
  const g = result as Partial<GenerateResponse>

  return (
    <SheetFrame meta={f.version !== undefined ? `Compile report · revision ${f.version}` : 'Compile report'}>
      <div className="ov">
        <Header facts={f} />
        <VerdictStrip result={result} />
        <Pipeline result={result} onOpenSheet={onOpenSheet} />

        {(f.coverage?.blocks?.length ?? 0) > 0 && f.coverage && (
          <Section label="Blocks and behaviour" count={f.coverage.blocks!.length} className="ov-section">
            <BlocksPanel coverage={f.coverage} />
          </Section>
        )}

        {(g.explanation || g.explanation_status || g.explanation_error) && (
        <Section label="Why this design" className="ov-section">
          <ExplanationPanel
            circuitId={result.circuit_id}
            token={token}
            explanation={g.explanation}
            status={g.explanation_status}
            error={g.explanation_error}
          />
        </Section>
        )}
      </div>
    </SheetFrame>
  )
}

/* ── 1. Header ─────────────────────────────────────────────────────────── */

function Header({ facts: f }: { facts: ReturnType<typeof designFacts> }) {
  return (
    <div className="ov-head">
      <p className="t-label ov-kicker">Requirement</p>
      <h1 className="t-title ov-intent">{f.intent ?? <span className="c-fg-3">The response carries no intent text.</span>}</h1>
      <dl className="ov-meta">
        {f.applicationClass && <Meta k="Class" v={f.applicationClass} />}
        {f.targetMcu && <Meta k="Board" v={f.targetMcu} />}
        {f.version !== undefined && <Meta k="Rev" v={`v${f.version}`} />}
        {f.generator && <Meta k="Generator" v={f.generator} />}
        <div className="ov-meta-item">
          <dt className="t-label">Design</dt>
          <dd className="t-data c-fg-2 truncate-1">{f.circuitId}</dd>
          <CopyButton value={f.circuitId} label="design id" />
        </div>
      </dl>
    </div>
  )
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div className="ov-meta-item">
      <dt className="t-label">{k}</dt>
      <dd className="t-data">{v}</dd>
    </div>
  )
}

/* ── 2. Verdict strip ──────────────────────────────────────────────────── */

function VerdictStrip({ result }: { result: DesignResult }) {
  const cov = result.validation_coverage
  if (!cov) {
    return (
      <div className="ov-empty" role="note">
        No claims on this design. The response carries no validation coverage, so nothing is counted here.
      </div>
    )
  }
  const c = claimCounts(cov)
  const props = cov.properties
  const proven = props?.filter(p => p.status === 'proven').length ?? 0

  const facts = [
    <div key="grade" className="ov-fact">
      <span className="t-label">Grade floor</span>
      <div className="ov-fact-body">
        <GradeChip grade={cov.grade_floor} title="The weakest grade among the critical, graded claims" />
        {!cov.grade_floor && <span className="t-small c-fg-3">no graded critical claim</span>}
      </div>
    </div>,
    <div key="defeaters" className="ov-fact">
      <span className="t-label">Open defeaters</span>
      <div className="ov-fact-body">
        {cov.open_defeaters.length > 0
          ? cov.open_defeaters.map(d => <Chip key={d} mono>{d}</Chip>)
          : <span className="t-small c-fg-2">none cited</span>}
      </div>
    </div>,
  ]
  if (props) {
    facts.push(
      <div key="props" className="ov-fact">
        <span className="t-label">Proved properties</span>
        <div className="ov-fact-body">
          <span className="t-data">proven {proven} of {props.length}</span>
          <Chip label tone={cov.properties_signed ? 'neutral' : 'none'} solid={!!cov.properties_signed}>
            {cov.properties_signed ? 'signed' : 'not signed'}
          </Chip>
        </div>
      </div>,
    )
  }

  return (
    <div role="group" aria-label={`Claims: ${claimCountsTitle(c)}`}>
      <div className="rule-grid ov-strip">
        <Counter tone="pass" glyph="✓" word="Holds" n={c.holds} />
        <Counter tone="warn" glyph="~" word="Holds, defeasible" n={c.defeasible} />
        <Counter tone="fail" glyph="✕" word="Fails" n={c.fails} />
        <Counter tone="none" glyph="–" word="Not assessed / out of scope" n={c.open} />
      </div>
      <div className="rule-grid ov-facts" style={{ gridTemplateColumns: `repeat(${facts.length}, minmax(0, 1fr))` }}>
        {facts}
      </div>
    </div>
  )
}

function Counter({ tone, glyph, word, n }: { tone: 'pass' | 'warn' | 'fail' | 'none'; glyph: string; word: string; n: number }) {
  return (
    <div className="ov-counter">
      <span className="t-label">{word}</span>
      <span className={`ov-counter-num c-${tone}`}>
        <span className="t-display">{n}</span>
        <span className="ov-counter-glyph" aria-hidden="true">{glyph}</span>
      </span>
    </div>
  )
}

/* ── 3. Pipeline ───────────────────────────────────────────────────────── */

interface Cell {
  sheet: SheetId
  name: string
  tone: ToneOrNeutral
  glyph?: string
  status: ReactNode
  detail?: ReactNode
}

function Pipeline({ result, onOpenSheet }: { result: DesignResult; onOpenSheet: (id: SheetId) => void }) {
  const f = designFacts(result)
  const cov = f.coverage
  const cells: Cell[] = []

  const v = f.validation
  cells.push(v
    ? {
        sheet: 'validation', name: 'Rules', tone: v.passed ? 'pass' : 'fail', glyph: v.passed ? '✓' : '✕',
        status: v.passed ? 'passed' : 'failed',
        detail: `${v.errors.length} ${v.errors.length === 1 ? 'error' : 'errors'} · ${v.warnings.length} ${v.warnings.length === 1 ? 'warning' : 'warnings'}`,
      }
    : { sheet: 'validation', name: 'Rules', tone: 'none', glyph: '–', status: 'no rule results' })

  const props = cov?.properties
  if (props && props.length > 0) {
    const proven = props.filter(p => p.status === 'proven').length
    const refuted = props.filter(p => p.status === 'refuted').length
    cells.push({
      sheet: 'validation', name: 'Proofs',
      tone: refuted > 0 ? 'fail' : proven === props.length ? 'pass' : 'warn',
      glyph: refuted > 0 ? '✕' : proven === props.length ? '✓' : '~',
      status: `proven ${proven} of ${props.length}`,
      detail: refuted > 0 ? `${refuted} refuted` : cov?.properties_signed ? 'signed' : 'not signed',
    })
  } else {
    cells.push({ sheet: 'validation', name: 'Proofs', tone: 'none', glyph: '–', status: 'no proved properties', detail: 'none on this response' })
  }

  cells.push(f.simulationJobId
    ? { sheet: 'simulation', name: 'Simulation', tone: 'neutral', status: 'queued', detail: 'open the sheet for the graded run' }
    : { sheet: 'simulation', name: 'Simulation', tone: 'none', glyph: '–', status: 'none', detail: 'no simulation for this design' })

  const fw = f.firmwareBuild
  if (fw) {
    const tone = firmwareTone(fw.status)
    cells.push({
      sheet: 'firmware', name: 'Firmware', tone,
      glyph: tone === 'pass' ? '✓' : tone === 'fail' ? '✕' : tone === 'none' ? '–' : undefined,
      status: fw.status === 'compiling' ? <>compiling <Cursor /></> : fw.status,
      detail: fw.board ?? (fw.status === 'none' || fw.status === 'unavailable' ? fw.message : undefined),
    })
  } else {
    cells.push({ sheet: 'firmware', name: 'Firmware', tone: 'none', glyph: '–', status: 'no build state', detail: 'open the sheet' })
  }

  cells.push(f.bomCount !== null
    ? { sheet: 'bom', name: 'BOM', tone: 'neutral', status: `${f.bomCount} ${f.bomCount === 1 ? 'line' : 'lines'}`, detail: 'prices dated, with their source' }
    : { sheet: 'bom', name: 'BOM', tone: 'neutral', status: 'open the sheet' })

  cells.push({
    sheet: 'schematic', name: 'Schematic', tone: 'neutral',
    status: f.componentCount !== null ? `${f.componentCount} components` : 'KiCad sheet',
    detail: f.netCount !== null ? `${f.netCount} nets · net labels` : 'net labels',
  })

  return (
    <Section label="Pipeline" className="ov-section">
      <div className="rule-grid ov-pipe">
        {cells.map(c => {
          const id = `ov-cell-${c.name.toLowerCase()}`
          const sheet = SHEET_BY_ID[c.sheet]
          return (
            <button
              key={c.name}
              type="button"
              className="ov-cell"
              onClick={() => onOpenSheet(c.sheet)}
              aria-label={`Open ${c.name.toLowerCase()} on sheet ${sheet.number}`}
              aria-describedby={id}
            >
              <span className="ov-cell-head">
                <span className="t-label">{sheet.number} · {c.name}</span>
                <ArrowRight size={14} strokeWidth={1.5} className="ov-cell-arrow" aria-hidden />
              </span>
              <span id={id} className="flex flex-col gap-1">
                <span className={`ov-cell-status ${c.tone !== 'neutral' ? `c-${c.tone}` : ''}`}>
                  {c.glyph && <span aria-hidden="true" className="t-data">{c.glyph}</span>}
                  {c.status}
                </span>
                {c.detail && <span className="ov-cell-detail">{c.detail}</span>}
              </span>
            </button>
          )
        })}
      </div>
    </Section>
  )
}
