'use client'

import { useEffect, useState } from 'react'
import { getFirmware, type FirmwareBuild } from '@/lib/api'

// Stage 5: firmware is shown only once it has compiled for the design's board.
// The design response says where the build stands; while it is compiling this
// polls GET /design/{id}/firmware every 3 s, and stops when it has passed or
// failed.

interface Props {
  circuitId: string | null
  token: string
  firmware: string | null
  build?: FirmwareBuild | null
}

const SETTLED = new Set(['compiled', 'failed', 'none'])

function initial(firmware: string | null, build?: FirmwareBuild | null): FirmwareBuild | null {
  if (build) return { ...build, firmware }
  // A design stored before Stage 5 carries source with no build record.
  return firmware ? { status: 'compiled', message: '', firmware } : null
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

export default function FirmwareViewer({ circuitId, token, firmware, build }: Props) {
  const [view, setView] = useState<FirmwareBuild | null>(() => initial(firmware, build))

  useEffect(() => {
    setView(initial(firmware, build))
  }, [firmware, build])

  const status = view?.status
  // A boolean, not the value: undefined → null would otherwise restart polling.
  const needsIni = status === 'compiled' && !view?.platformio_ini
  useEffect(() => {
    // Poll only while a build is in flight. A compiled view is fetched once
    // more, for its platformio.ini, which the design response leaves out.
    if (!circuitId || !token || !build) return
    if (status !== 'compiling' && !needsIni) return
    let stopped = false
    let timer: ReturnType<typeof setInterval> | undefined
    const poll = async () => {
      try {
        const next = await getFirmware(circuitId, token)
        if (stopped) return
        setView(next)
        if (SETTLED.has(next.status) && timer) clearInterval(timer)
      } catch {
        // A failed poll is retried on the next tick.
      }
    }
    poll()
    if (status === 'compiling') timer = setInterval(poll, 3000)
    return () => {
      stopped = true
      if (timer) clearInterval(timer)
    }
  }, [circuitId, token, build, status, needsIni])

  if (!view || view.status === 'none') {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        No firmware for this circuit type (passive circuits have no MCU code).
      </div>
    )
  }

  if (view.status !== 'compiled' || !view.firmware) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 border-b border-border bg-surface">
          <div className="text-xs font-mono text-muted">{view.board ?? view.target ?? 'firmware'}</div>
          <p className={`text-sm mt-1 ${view.status === 'failed' ? 'text-red-300' : 'text-cream'}`}>
            {view.status === 'compiling' && (
              <span className="inline-block w-2 h-2 rounded-full bg-lavender animate-pulse mr-2" />
            )}
            {view.message}
          </p>
        </div>
        {view.status === 'failed' && view.log && (
          <pre className="flex-1 p-4 text-xs font-mono text-muted overflow-auto leading-relaxed">{view.log}</pre>
        )}
      </div>
    )
  }

  const source = view.firmware
  const ini = view.platformio_ini ?? null
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <span className="text-xs text-muted font-mono">
          src/main.ino{view.board ? ` · compiled for the ${view.board}` : ''}
        </span>
        <div className="flex gap-4">
          {ini && (
            <button
              onClick={() => download('platformio.ini', ini)}
              className="text-xs text-lavender hover:text-lavender-dim transition-colors"
            >
              Download platformio.ini
            </button>
          )}
          <button
            onClick={() => download('main.ino', source)}
            className="text-xs text-lavender hover:text-lavender-dim transition-colors"
          >
            Download .ino
          </button>
        </div>
      </div>
      <pre className="flex-1 p-4 text-sm font-mono text-cream-dim overflow-auto leading-relaxed">
        {source}
      </pre>
    </div>
  )
}
