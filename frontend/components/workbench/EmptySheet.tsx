'use client'

/**
 * The workbench before a design is loaded: a quiet "No design loaded", one line on what to do,
 * and the sheet index — the seven sheets, numbered, one line each on what they will contain.
 */
import { EmptyState, Kbd, SheetFrame } from '@/components/ui'
import type { SheetDef, SheetId } from './sheets'

export function EmptySheet({ sheets, active, demo }: { sheets: SheetDef[]; active: SheetId; demo: boolean }) {
  return (
    <SheetFrame meta="No design loaded">
      <div className="idx">
        <EmptyState title="No design loaded">
          {demo
            ? 'Pick a recorded example in the requirement panel to open its schematic, firmware, simulation, BOM and validation.'
            : 'Describe a circuit in the requirement panel. The compiler writes the requirement down, derives the design, and fills these sheets.'}
        </EmptyState>

        <h3 className="t-label mt-4 pb-2 hairline-b">Sheet index</h3>
        <ol>
          {sheets.map(s => (
            <li key={s.id} className="idx-row" aria-current={s.id === active ? 'true' : undefined}>
              <span className="idx-num" aria-hidden="true">{s.number}</span>
              <span className="idx-name">{s.title}</span>
              <span className="idx-about">{s.about}</span>
            </li>
          ))}
        </ol>

        <p className="t-small c-fg-3 mt-6 flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="inline-flex items-center gap-1.5"><Kbd>Alt</Kbd><Kbd>0</Kbd>–<Kbd>6</Kbd> open a sheet</span>
          <span className="inline-flex items-center gap-1.5"><Kbd>Ctrl</Kbd><Kbd>B</Kbd> show or hide the requirement panel</span>
        </p>
      </div>
    </SheetFrame>
  )
}
