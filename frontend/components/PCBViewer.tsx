'use client'

import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import { compilePCB, PCBCompileResponse } from '@/lib/api'
import BoardVerification from '@/components/BoardVerification'
import { Button, Callout, Cursor, EmptyState, Section, SheetFrame } from '@/components/ui'

// three.js needs the browser (WebGL, document): never server-render it — the
// same rule as the kicanvas schematic viewer.
const Board3DView = dynamic(() => import('@/components/Board3DView'), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center t-small c-fg-2">
      Loading 3D view…<Cursor />
    </div>
  ),
})

interface Props {
  netlist?: Record<string, any>
  token: string
}

// The layout engine runs inside the API (POST /pcb/compile), not as a separate
// service. It used to be its own process on port 8001 that the browser called
// directly, which only ever worked on a developer machine: in a deployed build
// `localhost:8001` resolves to the *visitor's* computer, and an http:// call
// from an https:// page is blocked as mixed content regardless.

export default function PCBViewer({ netlist, token }: Props) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<PCBCompileResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'3d' | '2d'>('3d')

  useEffect(() => {
    if (!netlist) return

    let cancelled = false
    setLoading(true)
    setError(null)

    compilePCB(netlist, token)
      .then((resData) => {
        if (cancelled) return
        setData(resData)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'PCB compilation failed.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [netlist, token])

  if (!netlist) {
    return (
      <SheetFrame>
        <EmptyState title="No PCB netlist generated yet.">
          The layout engine needs a design with a board netlist.
        </EmptyState>
      </SheetFrame>
    )
  }

  const stats = data?.stats
  const ready = !!data && !loading && !error
  const show3d = ready && !!data?.scene && mode === '3d'
  const show2d = ready && !!data?.svg && (mode === '2d' || !data?.scene)
  const report = data?.verification?.findings ? data.verification : null
  const warnings = data?.warnings ?? []

  const meta = stats?.name ? (
    <span className="t-data">
      {stats.name}
      {stats.size_mm && <span className="c-fg-3"> · {stats.size_mm[0]} × {stats.size_mm[1]} mm</span>}
    </span>
  ) : (
    <span>Placement and routing — experimental</span>
  )

  const actions = data?.stats ? (
    <div className="pcb-seg" role="group" aria-label="Board view">
      {(['2d', '3d'] as const).map(m => (
        <Button
          key={m}
          size="sm"
          variant="secondary"
          onClick={() => setMode(m)}
          aria-pressed={mode === m}
          disabled={m === '3d' && !data.scene}
        >
          {m.toUpperCase()}
        </Button>
      ))}
    </div>
  ) : undefined

  return (
    <SheetFrame well padded={false} meta={meta} actions={actions}>
      <style>{CSS}</style>
      {/* The viewer fills the sheet; the verifier and the engine's warnings follow
          below it, their heading left in view so they are never out of sight. */}
      <div className="pcb-stage">
        <div className="pcb-note">
          <Callout tone="warn" title="Experimental layout">
            Placement is tested; routing is not. Unrouted connections are drawn as dashed ratsnest,
            and no fabrication files are produced from this board.
          </Callout>
        </div>

        {stats && (
          <div className="sb pcb-stats" aria-label="Board statistics">
            {stats.drc_errors !== undefined && (
              <span className="sb-cell">
                <span className="sb-k">DRC errors</span>
                {stats.drc_errors === 0
                  ? <span className="c-pass">✓ 0</span>
                  : <span className="c-fail">✕ {stats.drc_errors}</span>}
              </span>
            )}
            {stats.unrouted !== undefined && (
              <span className="sb-cell" title="Connections the router did not complete">
                <span className="sb-k">Unrouted</span>
                {stats.unrouted === 0
                  ? <span className="c-pass">✓ 0</span>
                  : <span className="c-warn">~ {stats.unrouted}</span>}
              </span>
            )}
            {stats.connections !== undefined && (
              <span className="sb-cell">
                <span className="sb-k">Routed</span>
                <span className="sb-v">{stats.routed}/{stats.connections}</span>
              </span>
            )}
            {stats.components !== undefined && (
              <span className="sb-cell"><span className="sb-k">Parts</span><span className="sb-v">{stats.components}</span></span>
            )}
            {stats.nets !== undefined && (
              <span className="sb-cell"><span className="sb-k">Nets</span><span className="sb-v">{stats.nets}</span></span>
            )}
            {stats.vias !== undefined && (
              <span className="sb-cell sb-opt"><span className="sb-k">Vias</span><span className="sb-v">{stats.vias}</span></span>
            )}
            {stats.copper_mm !== undefined && (
              <span className="sb-cell sb-opt">
                <span className="sb-k">Copper</span>
                <span className="sb-v">{stats.copper_mm}<span className="unit">mm</span></span>
              </span>
            )}
            <span className="sb-fill" />
            {report && (
              <a href="#board-verification" className="sb-cell pcb-jump" title="Jump to the board verifier's findings">
                <span className="sb-k">Verifier</span>
                <span className={report.ok ? 'c-pass' : 'c-fail'}>{report.ok ? '✓ ok' : '✕ fails'}</span>
                <span className="c-fg-3" aria-hidden="true">↓</span>
              </a>
            )}
          </div>
        )}

        <div className="pcb-view">
          {loading && (
            <div className="pcb-center t-ui c-fg-2" role="status">
              Compiling PCB layout…<Cursor label="Compiling" />
            </div>
          )}

          {error && !loading && (
            <div className="pcb-center">
              <Callout tone="fail" title="PCB layout failed" role="alert" className="pcb-msg">
                <span className="t-data" style={{ overflowWrap: 'anywhere', whiteSpace: 'pre-wrap' }}>{error}</span>
              </Callout>
            </div>
          )}

          {/* Every component was dropped. The engine still returns a valid SVG —
              an empty board renders as a plain rectangle and reads as success,
              which is exactly how this went unnoticed. Say so explicitly. */}
          {ready && data?.stats?.components === 0 && (
            <div className="pcb-overlay-note">
              <Callout tone="fail" title="Empty board — no components placed" className="pcb-msg">
                Every component was dropped before layout. See the warnings below
                for which parts and why.
              </Callout>
            </div>
          )}

          {show3d && data?.scene && (
            <div className="absolute inset-0">
              <Board3DView scene={data.scene} />
            </div>
          )}

          {show2d && (
            <div className="pcb-2d">
              <div
                id="pcb-panel"
                className="pcb-svg"
                dangerouslySetInnerHTML={{ __html: data!.svg }}
              />
            </div>
          )}
        </div>
      </div>

      {(report || warnings.length > 0) && !loading && (
        <div className="pcb-below">
          {/* The verifier's findings. The board stays on screen when they fail
              (owner's decision 2026-10-17); refusal belongs at fab-file export. */}
          {report && <BoardVerification report={report} />}

          {/* Warnings — open by default. A warning here means the board on
              screen is not the board that was asked for; collapsed, that reads as
              no warning at all. */}
          {warnings.length > 0 && (
            <Section label="PCB engine warnings" count={warnings.length} collapsible>
              <ul className="pcb-warn-list">
                {warnings.map((w, idx) => (
                  <li key={idx} className="t-data">
                    <span className="c-warn" aria-hidden="true">~</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>
      )}
    </SheetFrame>
  )
}

// Layout for this sheet only. Tokens from globals.css; no colour that is not a verdict.
const CSS = `
.pcb-seg { display: inline-flex; }
.pcb-seg > .btn + .btn { margin-left: -1px; }
.pcb-seg > .btn[aria-pressed='true']:hover:not(:disabled) { background: var(--fg); color: var(--bench-0); }
.pcb-stage { height: calc(100% - 44px); min-height: 420px; display: flex; flex-direction: column; }
.pcb-note { padding: 12px 16px; background: var(--bench-1); border-bottom: 1px solid var(--line); flex: none; }
.pcb-stats { border-top: 0; border-bottom: 1px solid var(--line); flex: none; overflow-x: auto; scrollbar-width: none; }
.pcb-stats .sb-cell:first-child { padding-left: 16px; }
.pcb-jump { border-right: 0; border-left: 1px solid var(--line); padding-right: 16px; color: inherit; text-decoration: none; }
.pcb-jump:hover { background: var(--bench-3); }
.pcb-view { position: relative; flex: 1; min-height: 0; background: var(--bench-0); container-type: size; }
.pcb-center { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 24px; }
.pcb-msg { max-width: 560px; width: 100%; }
.pcb-overlay-note { position: absolute; top: 16px; left: 16px; right: 16px; z-index: 2; display: flex; justify-content: center; }
.pcb-overlay-note .callout { background: var(--bench-1); }
.pcb-2d { position: absolute; inset: 0; overflow: auto; display: flex; padding: 24px; }
.pcb-svg { margin: auto; border: 1px solid var(--line); line-height: 0; }
.pcb-svg svg { display: block; width: auto; height: auto; max-width: calc(100cqw - 50px); max-height: calc(100cqh - 50px); }
.pcb-below { background: var(--bench-1); border-top: 1px solid var(--line); padding: 8px 32px 48px; }
.pcb-below .section + .section { margin-top: 32px; }
.pcb-warn-list { display: flex; flex-direction: column; }
.pcb-warn-list li { display: flex; gap: 8px; min-height: var(--h-row); align-items: center; border-bottom: 1px solid var(--line); color: var(--fg-2); }
@media (max-width: 719.98px) {
  .pcb-below { padding: 8px 16px 32px; }
  .pcb-note { padding: 8px 16px; }
}
`
