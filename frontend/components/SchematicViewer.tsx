'use client'

// kicanvas requires dynamic import with ssr:false — it uses browser-only APIs.
// Never SSR this component. (CLAUDE.md Rule 5) Nothing below touches document,
// Blob or URL at module level: only inside effects and event handlers.

import { useEffect, useRef, useState } from 'react'
import { Download } from 'lucide-react'
import { Button, Callout, CopyButton, Cursor, EmptyState, ICON, SheetFrame } from '@/components/ui'
import { SourceView } from '@/components/FirmwareViewer'

interface Props {
  schematic: string
}

const KICANVAS_CDN = 'https://kicanvas.org/kicanvas/kicanvas.js'

// One load per page. A plain variable, not a DOM read, so nothing runs at module load. Without it,
// React 18 StrictMode's second effect run found the first run's <script> already in <head>, took it as
// loaded before it had loaded or failed, and mounted an unregistered <kicanvas-embed>: a blocked CDN
// then printed the source as one run-on paragraph instead of falling back.
let kicanvasLoad: Promise<boolean> | null = null

function loadKicanvas(): Promise<boolean> {
  if (kicanvasLoad) return kicanvasLoad
  kicanvasLoad = new Promise((resolve) => {
    if (customElements.get('kicanvas-embed')) {
      resolve(true)
      return
    }
    const script = document.createElement('script')
    script.type = 'module'
    script.src = KICANVAS_CDN
    script.onload = () => resolve(true)
    script.onerror = () => {
      // The raw source fallback below still works. Forget the attempt so a later mount can retry.
      script.remove()
      kicanvasLoad = null
      resolve(false)
    }
    document.head.appendChild(script)
  })
  return kicanvasLoad
}

function download(name: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export default function SchematicViewer({ schematic }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const [ready, setReady] = useState(false)
  const [showSource, setShowSource] = useState(false)

  useEffect(() => {
    if (!schematic) return

    // `cancelled` guards against React 18 StrictMode double-invoking this
    // effect: without it the first async callback can write into a container
    // that the second run has already replaced.
    let cancelled = false
    setReady(false)

    loadKicanvas().then((ok) => {
      if (cancelled) return
      if (!ok) {
        setFailed(true)
        return
      }
      const host = containerRef.current
      if (!host) return

      host.replaceChildren()

      // Pass the schematic as an inline <kicanvas-source> child rather than a
      // blob: URL on `src`.
      //
      // Two reasons this matters:
      //  1. kicanvas infers the document type from the file extension in `src`.
      //     A blob: URL has no extension, so it could not tell a .kicad_sch
      //     from anything else and parsed nothing — the canvas mounted but
      //     stayed empty.
      //  2. The old code revoked the blob URL in effect cleanup, which under
      //     StrictMode revoked it before kicanvas had finished reading it.
      //
      // Built with createElement + textContent rather than an innerHTML
      // template string: the schematic embeds ir.intent, which is user-supplied
      // prompt text, so interpolating it into HTML was an injection vector.
      const embed = document.createElement('kicanvas-embed')
      embed.setAttribute('controls', 'full')
      embed.setAttribute('style', 'width:100%;height:100%;display:block;')

      const source = document.createElement('kicanvas-source')
      source.setAttribute('type', 'schematic')
      source.textContent = schematic

      embed.appendChild(source)
      host.appendChild(embed)
      setReady(true)
    })

    return () => {
      cancelled = true
    }
  }, [schematic])

  if (!schematic) {
    return (
      <SheetFrame>
        <EmptyState title="No schematic generated yet." />
      </SheetFrame>
    )
  }

  // Without the renderer the raw source is the schematic: it is shown, and the toggle is moot.
  const sourceShown = showSource || failed
  const lines = schematic.split('\n').length
  const narrowHide = 'max-[719.98px]:sr-only'

  return (
    <SheetFrame
      well
      padded={false}
      scroll={false}
      meta={
        <>
          <span className="t-data">schematic.kicad_sch</span>
          {' · '}
          {failed ? 'renderer unavailable, raw source' : sourceShown ? <><span className="t-data">{lines}</span> lines</> : 'net labels'}
        </>
      }
      actions={
        <>
          <Button
            size="sm"
            aria-pressed={sourceShown}
            disabled={failed}
            title={failed ? 'The renderer did not load: the source is all there is to show' : undefined}
            onClick={() => setShowSource(s => !s)}
          >
            Source
          </Button>
          <CopyButton value={schematic} label=".kicad_sch source" />
          <Button size="sm" icon={<Download {...ICON} />} onClick={() => download('schematic.kicad_sch', schematic)}>
            <span className={narrowHide}>Download .kicad_sch</span>
          </Button>
        </>
      }
    >
      <div className="relative h-full flex flex-col">
        {failed && (
          <div className="flex-none px-4 py-2 border-b border-line bg-bench-1">
            <Callout tone="info">Schematic renderer unavailable — showing the raw .kicad_sch.</Callout>
          </div>
        )}
        {/* The kicanvas host stays mounted while the source is shown, so toggling back is instant. */}
        <div className={`relative flex-1 min-h-0 ${sourceShown ? 'hidden' : ''}`}>
          <div className="absolute inset-0" ref={containerRef} />
          {!ready && !failed && (
            <p className="absolute left-4 top-3 t-small c-fg-3 pointer-events-none">
              <Cursor label="Loading" /> Loading the schematic renderer…
            </p>
          )}
        </div>
        {sourceShown && (
          <div className="flex-1 min-h-0">
            <SourceView text={schematic} label="Schematic source, .kicad_sch" />
          </div>
        )}
      </div>
    </SheetFrame>
  )
}
