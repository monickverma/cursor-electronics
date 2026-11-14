'use client'

/**
 * The demo statement, in full, at the top of the requirement panel. A statement about evidence,
 * so it is a warn Callout. Collapsible; it collapses once a design is open (the top-bar chip and
 * the status bar keep saying DEMO), and can always be reopened.
 */
import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Callout } from '@/components/ui'

export function DemoNotice({ repoUrl, designOpen }: { repoUrl: string; designOpen: boolean }) {
  const [open, setOpen] = useState(!designOpen)
  useEffect(() => { if (designOpen) setOpen(false) }, [designOpen])

  return (
    <Callout tone="warn" role="status">
      <button type="button" className="disclosure" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        {open ? <ChevronDown size={12} strokeWidth={1.5} aria-hidden /> : <ChevronRight size={12} strokeWidth={1.5} aria-hidden />}
        <span className="callout-title">Demo mode — recorded results.</span>
      </button>
      {open && (
        <p className="t-small mt-1.5">
          No backend is attached to this deployment. The examples below are real outputs of the
          deterministic pipeline (generator, ngspice, PlatformIO, BOM), recorded locally; the
          requirement was entered through the form, not the LLM.{' '}
          <a className="link" href={`${repoUrl}#readme`} target="_blank" rel="noopener noreferrer">Run it locally</a>{' '}
          to describe your own circuit.
        </p>
      )}
    </Callout>
  )
}
