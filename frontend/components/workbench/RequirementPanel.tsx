'use client'

/**
 * The requirement panel (left): hosts ChatPanel. Resizable (300–560px, width kept in localStorage),
 * collapsible from the top bar or Ctrl/⌘+B. Under 1100px wide it becomes an overlay drawer.
 * Collapsed, it stays mounted (hidden) so the conversation is not lost.
 *
 * The resize handle is a focusable `role="separator"` with aria-valuenow; ←/→ move it 16px
 * (Shift: 48px), Home/End jump to the limits.
 */
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { PanelLeftClose } from 'lucide-react'
import { ICON } from '@/components/ui'
import { PANEL_MAX, PANEL_MIN, usePanelWidth } from './hooks'

interface Props {
  id: string
  open: boolean
  onClose: () => void
  /** Overlay drawer instead of a docked column. */
  drawer: boolean
  /** Shown above the console (e.g. the demo statement). */
  notice?: ReactNode
  /** Right side of the panel header, e.g. the revision being edited. */
  headMeta?: ReactNode
  children: ReactNode
}

export function RequirementPanel({ id, open, onClose, drawer, notice, headMeta, children }: Props) {
  const [width, setWidth] = usePanelWidth()
  const [dragging, setDragging] = useState(false)
  const start = useRef<{ x: number; w: number } | null>(null)

  // Escape closes the drawer.
  useEffect(() => {
    if (!drawer || !open) return
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawer, open, onClose])

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    start.current = { x: e.clientX, w: width }
    setDragging(true)
  }
  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!start.current) return
    setWidth(start.current.w + (e.clientX - start.current.x))
  }
  function onPointerUp(e: PointerEvent<HTMLDivElement>) {
    if (!start.current) return
    start.current = null
    setDragging(false)
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already released */ }
  }
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const step = e.shiftKey ? 48 : 16
    if (e.key === 'ArrowLeft') { e.preventDefault(); setWidth(width - step) }
    else if (e.key === 'ArrowRight') { e.preventDefault(); setWidth(width + step) }
    else if (e.key === 'Home') { e.preventDefault(); setWidth(PANEL_MIN) }
    else if (e.key === 'End') { e.preventDefault(); setWidth(PANEL_MAX) }
  }

  return (
    <>
      {drawer && open && <div className="req-scrim" aria-hidden="true" onClick={onClose} />}
      <aside
        id={id}
        className={`req ${drawer ? 'req-drawer' : ''}`}
        style={drawer ? undefined : { width }}
        hidden={!open}
        aria-label="Requirement"
      >
        <div className="req-head">
          <span className="t-label">Requirement</span>
          {headMeta && <span className="t-data c-fg-3 truncate-1">{headMeta}</span>}
          <button
            type="button"
            className="btn btn-ghost btn-square btn-sm"
            style={{ marginLeft: 'auto' }}
            onClick={onClose}
            aria-label="Hide requirement panel"
            title="Hide requirement panel (Ctrl+B)"
          >
            <PanelLeftClose {...ICON} />
          </button>
        </div>
        {notice && <div className="req-notice">{notice}</div>}
        <div className="req-body">{children}</div>

        {!drawer && (
          <div
            className="req-handle"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize requirement panel"
            aria-controls={id}
            aria-valuenow={width}
            aria-valuemin={PANEL_MIN}
            aria-valuemax={PANEL_MAX}
            tabIndex={0}
            data-dragging={dragging ? 'true' : undefined}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onKeyDown={onKeyDown}
            onDoubleClick={() => setWidth(380)}
          />
        )}
      </aside>
    </>
  )
}
