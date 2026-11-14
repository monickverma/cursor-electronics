'use client'

/**
 * SheetFrame — one numbered sheet of the drawing set: a 32px header and a body that scrolls.
 * Make it the ROOT of your panel; it fills the sheet area (height 100%).
 *
 *   <SheetFrame
 *     meta={<>src/main.ino · compiled for the {board}</>}
 *     actions={<Button size="sm" icon={<Download {...ICON} />}>Download .ino</Button>}
 *   >
 *     <pre>…</pre>
 *   </SheetFrame>
 *
 *   <SheetFrame well padded={false}>  …kicanvas / 3D canvas edge to edge on --bench-0…  </SheetFrame>
 *
 * number / title: optional — the workbench provides them for the sheet you are rendered in
 *   ("03", "Firmware"). Pass them only to override.
 * meta:    one line after the title (truncated), e.g. what the sheet shows and for which board.
 * actions: right-aligned, use <Button size="sm">.
 * padded:  default true — 24px/32px reading margins. false for canvases and full-bleed tables.
 * well:    the body is a --bench-0 canvas well.
 * scroll:  default true. false when the child manages its own scrolling (canvases).
 * While a panel renders without a SheetFrame, the workbench draws a plain header for it; as soon
 * as a SheetFrame is inside the sheet, that header hides itself — there is never a double header.
 */
import { createContext, useContext, type ReactNode } from 'react'

export interface SheetInfo {
  /** Two digits, "00"–"06". */
  number: string
  title: string
}

export const SheetContext = createContext<SheetInfo | null>(null)

/** The sheet you are rendered in, or null outside the workbench. */
export function useSheet(): SheetInfo | null {
  return useContext(SheetContext)
}

export interface SheetFrameProps {
  number?: string
  title?: string
  meta?: ReactNode
  actions?: ReactNode
  children: ReactNode
  padded?: boolean
  well?: boolean
  scroll?: boolean
  className?: string
  bodyClassName?: string
  /** Optional id for the body (e.g. an existing anchor such as `pcb-panel` lives inside). */
  bodyId?: string
}

export function SheetFrame({
  number, title, meta, actions, children,
  padded = true, well = false, scroll = true, className = '', bodyClassName = '', bodyId,
}: SheetFrameProps) {
  const sheet = useSheet()
  const n = number ?? sheet?.number
  const t = title ?? sheet?.title ?? ''
  return (
    <section className={`sheet-frame ${className}`}>
      <SheetHeader number={n} title={t} meta={meta} actions={actions} />
      <div
        id={bodyId}
        className={[
          'sheet-body',
          padded ? 'sheet-body-pad' : '',
          well ? 'sheet-well' : '',
          bodyClassName,
        ].filter(Boolean).join(' ')}
        style={scroll ? undefined : { overflow: 'hidden' }}
      >
        {children}
      </div>
    </section>
  )
}

/** The 32px header alone — `SHEET 03  Firmware  meta …  [actions]`. Used by SheetFrame and the workbench. */
export function SheetHeader({ number, title, meta, actions }: {
  number?: string
  title: string
  meta?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="sheet-head">
      <div className="sheet-head-id">
        {number && <span className="t-label">Sheet {number}</span>}
        <h2 className="t-label sheet-head-title">{title}</h2>
      </div>
      {meta && <div className="sheet-head-meta">{meta}</div>}
      {actions && <div className="sheet-head-actions">{actions}</div>}
    </header>
  )
}
