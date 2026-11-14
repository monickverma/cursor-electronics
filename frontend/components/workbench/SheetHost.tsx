'use client'

/**
 * Hosts one sheet under the tabs. Provides the sheet's number and title to a SheetFrame inside,
 * and draws a plain sheet header for panels that do not bring a SheetFrame yet. CSS hides that
 * header as soon as a `.sheet-frame` is present (`.sheet-host:has(.sheet-frame)`), so a migrated
 * panel never gets a double header.
 */
import type { ReactNode } from 'react'
import { SheetContext, SheetHeader } from '@/components/ui'
import type { SheetDef } from './sheets'

export function SheetHost({ sheet, children }: { sheet: SheetDef; children: ReactNode }) {
  return (
    <SheetContext.Provider value={{ number: sheet.number, title: sheet.title }}>
      <div className="sheet-host" id="sheet-host" role="region" aria-label={`Sheet ${sheet.number} ${sheet.title}`}>
        <div className="sheet-fallback-head">
          <SheetHeader number={sheet.number} title={sheet.title} />
        </div>
        <div className="sheet-host-body">{children}</div>
      </div>
    </SheetContext.Provider>
  )
}
