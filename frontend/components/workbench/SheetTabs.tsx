'use client'

/**
 * Sheet tabs — 36px. Plain buttons (tests find them by role "button" and exact name), so the
 * sheet number and any badge are aria-hidden: the accessible name is the label alone.
 * The active tab carries aria-current and a 2px white rule, and joins the sheet below.
 */
import { useEffect, useRef } from 'react'
import type { SheetDef, SheetId } from './sheets'

interface Props {
  sheets: SheetDef[]
  active: SheetId
  onSelect: (id: SheetId) => void
  /** Rule-error count for the Validation tab. Shown only when > 0. */
  validationErrors?: number
}

export function SheetTabs({ sheets, active, onSelect, validationErrors = 0 }: Props) {
  const navRef = useRef<HTMLElement>(null)
  // On a narrow screen the tabs scroll sideways: keep the active one in view (Alt+n, Overview links).
  useEffect(() => {
    const el = navRef.current?.querySelector<HTMLElement>('[aria-current="true"]')
    el?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [active])

  return (
    <nav className="tabs" aria-label="Sheets" ref={navRef}>
      {sheets.map(s => {
        const isActive = s.id === active
        const badge = s.id === 'validation' && validationErrors > 0 ? validationErrors : null
        return (
          <button
            key={s.id}
            type="button"
            className="tab"
            aria-current={isActive ? 'true' : undefined}
            aria-describedby={badge ? 'tab-validation-errors' : undefined}
            onClick={() => onSelect(s.id)}
            title={`Sheet ${s.number} (Alt+${Number(s.number)})`}
          >
            <span className="tab-num" aria-hidden="true">{s.number}</span>
            {s.id === 'pcb'
              ? <span className="tab-label">PCB <span className="tab-sub">(experimental)</span></span>
              : <span className="tab-label">{s.label}</span>}
            {badge !== null && <span className="tab-badge" aria-hidden="true">{badge}</span>}
          </button>
        )
      })}
      <div className="tabs-fill" />
      {validationErrors > 0 && (
        <span id="tab-validation-errors" className="sr-only">{validationErrors} rule error(s)</span>
      )}
    </nav>
  )
}
