'use client'

/**
 * Section — a lettered heading on a hairline, then content. Sections stack with 32px between them.
 *
 *   <Section label="Claims" count={claims.length}>…</Section>
 *   <Section label="Proved properties" count={n} actions={<Button size="sm">…</Button>}>…</Section>
 *   <Section label="Rejected substitutes" collapsible defaultOpen={false}>…</Section>
 *
 * label:  short, rendered uppercase in .t-label. As a heading it is an <h3>.
 * count:  mono number after the label (a fact from the data; omit rather than print 0 you did not count).
 * collapsible: the label becomes a toggle button (aria-expanded). Its accessible name is the label
 *   plus the count — do NOT give a collapsible section a label equal to a sheet name
 *   ("Firmware", "BOM", "Validation", …): tests find the sheet tabs by exact button name.
 */
import { useId, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface Props {
  label: string
  count?: number
  actions?: ReactNode
  collapsible?: boolean
  defaultOpen?: boolean
  children: ReactNode
  className?: string
  id?: string
}

export function Section({ label, count, actions, collapsible = false, defaultOpen = true, children, className = '', id }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const bodyId = useId()
  const shown = !collapsible || open
  return (
    <section className={`section ${className}`} id={id}>
      <div className="section-head">
        {collapsible ? (
          <h3>
            <button
              type="button"
              className="section-toggle"
              aria-expanded={open}
              aria-controls={bodyId}
              onClick={() => setOpen(o => !o)}
            >
              {open ? <ChevronDown size={12} strokeWidth={1.5} aria-hidden /> : <ChevronRight size={12} strokeWidth={1.5} aria-hidden />}
              <span className="t-label">{label}</span>
              {count !== undefined && <span className="section-count">{count}</span>}
            </button>
          </h3>
        ) : (
          <>
            <h3 className="t-label">{label}</h3>
            {count !== undefined && <span className="section-count">{count}</span>}
          </>
        )}
        {actions && <div className="section-actions">{actions}</div>}
      </div>
      <div id={bodyId} hidden={!shown}>
        {shown && children}
      </div>
    </section>
  )
}
