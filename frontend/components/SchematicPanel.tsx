'use client'

/**
 * The Schematic window: the interactive drawing, or the KiCad file itself.
 *
 * Both show the same design. The drawing is laid out here from the CircuitIR;
 * the KiCad view is the generated `.kicad_sch` rendered by kicanvas, which is
 * what opens in KiCad.
 */

import dynamic from 'next/dynamic'
import { useState } from 'react'
import SchematicDrawing from '@/components/SchematicDrawing'

// kicanvas uses browser-only APIs: never server-render it (CLAUDE.md rule 5).
const SchematicViewer = dynamic(() => import('@/components/SchematicViewer'), { ssr: false })

interface Finding { field: string; message: string }
interface Props {
  schematic: string
  ir: unknown
  findings?: Finding[]
}

export default function SchematicPanel({ schematic, ir, findings }: Props) {
  const [mode, setMode] = useState<'drawing' | 'kicad'>('drawing')
  const tab = (id: 'drawing' | 'kicad', label: string) => (
    <button
      type="button"
      aria-pressed={mode === id}
      onClick={() => setMode(id)}
      className={`min-h-[30px] px-3 font-mono text-xs border-[1.5px] border-border ${
        mode === id ? 'bg-cream text-dark' : 'text-cream'}`}
    >
      {label}
    </button>
  )
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center gap-1.5 px-3 pt-2">
        {tab('drawing', 'Drawing')}
        {tab('kicad', 'KiCad file')}
      </div>
      <div className="flex-1 min-h-0">
        {mode === 'drawing'
          ? <SchematicDrawing ir={ir} findings={findings} />
          : <SchematicViewer schematic={schematic} />}
      </div>
    </div>
  )
}
