'use client'

// kicanvas requires dynamic import with ssr:false — it uses browser-only APIs.
// Never SSR this component. (CLAUDE.md Rule 5)

import { useEffect, useRef, useState } from 'react'

interface Props {
  schematic: string
}

const KICANVAS_CDN = 'https://kicanvas.org/kicanvas/kicanvas.js'

function loadKicanvas(): Promise<boolean> {
  return new Promise((resolve) => {
    if (document.querySelector(`script[src="${KICANVAS_CDN}"]`)) {
      resolve(true)
      return
    }
    const script = document.createElement('script')
    script.type = 'module'
    script.src = KICANVAS_CDN
    script.onload = () => resolve(true)
    script.onerror = () => resolve(false) // raw text fallback below still works
    document.head.appendChild(script)
  })
}

export default function SchematicViewer({ schematic }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!schematic) return

    // `cancelled` guards against React 18 StrictMode double-invoking this
    // effect: without it the first async callback can write into a container
    // that the second run has already replaced.
    let cancelled = false

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
    })

    return () => {
      cancelled = true
    }
  }, [schematic])

  if (!schematic) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        No schematic generated yet.
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 relative" ref={containerRef}>
        {failed && (
          <div className="absolute inset-0 flex items-center justify-center text-muted text-sm">
            Schematic renderer unavailable — see raw .kicad_sch below.
          </div>
        )}
      </div>

      {/* Raw KiCad text fallback — always accessible */}
      <details className="border-t border-border">
        <summary className="px-4 py-2 text-xs text-muted cursor-pointer hover:text-cream select-none">
          View raw .kicad_sch
        </summary>
        <pre className="p-4 text-xs font-mono text-cream-dim overflow-auto max-h-48 bg-surface">
          {schematic}
        </pre>
      </details>
    </div>
  )
}
