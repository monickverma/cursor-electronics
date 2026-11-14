'use client'

import { useEffect, useRef, useState } from 'react'
import { Download } from 'lucide-react'
import { getFirmware, type FirmwareBuild } from '@/lib/api'
import { Button, Callout, CopyButton, Cursor, EmptyState, ICON, SheetFrame } from '@/components/ui'

// Stage 5: firmware is shown only once it has compiled for the design's board.
// The design response says where the build stands; while it is compiling this
// polls GET /design/{id}/firmware every 3 s, and stops when it has passed or
// failed.

interface Props {
  circuitId: string | null
  token: string
  firmware: string | null
  build?: FirmwareBuild | null
  /** Called (from an effect) whenever a poll brings a newer build state, so the page can follow it. */
  onBuild?: (build: FirmwareBuild) => void
}

const SETTLED = new Set(['compiled', 'failed', 'none'])

function initial(firmware: string | null, build?: FirmwareBuild | null): FirmwareBuild | null {
  // The source prop wins; a build that already carries its source (one the page took from a poll) keeps it.
  if (build) return { ...build, firmware: firmware ?? build.firmware ?? null }
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

/**
 * Source with a line-number gutter. One <pre> only (the gutter is a div, aria-hidden and not
 * selectable), so copying or selecting the code never picks up the numbers. Fills its parent and
 * scrolls both ways; the gutter stays put when scrolling sideways.
 */
export function SourceView({ text, label }: { text: string; label: string }) {
  const lines = text.endsWith('\n') ? text.slice(0, -1).split('\n') : text.split('\n')
  const numbers = lines.map((_, i) => i + 1).join('\n')
  return (
    <div className="h-full overflow-auto bg-bench-0" role="region" aria-label={label} tabIndex={0}>
      <div className="flex min-w-max min-h-full">
        <div
          aria-hidden="true"
          className="t-data sticky left-0 flex-none select-none whitespace-pre text-right text-fg-3 bg-bench-0 border-r border-line pl-4 pr-3 py-3"
        >
          {numbers}
        </div>
        <pre className="t-data flex-1 text-fg pl-4 pr-8 py-3 m-0">{text}</pre>
      </div>
    </div>
  )
}

export default function FirmwareViewer({ circuitId, token, firmware, build, onBuild }: Props) {
  const [view, setView] = useState<FirmwareBuild | null>(() => initial(firmware, build))
  // What the last poll brought: reported to the page from an effect, never during render.
  const [polled, setPolled] = useState<FirmwareBuild | null>(null)
  const onBuildRef = useRef(onBuild)
  onBuildRef.current = onBuild
  const reported = useRef<string | null>(null)

  useEffect(() => {
    setView(initial(firmware, build))
  }, [firmware, build])

  const status = view?.status
  // A boolean, not the value: undefined → null would otherwise restart polling.
  const needsIni = status === 'compiled' && !view?.platformio_ini
  // Likewise a boolean: the page hands each polled build back as a new `build` object (onBuild),
  // and that must not restart the interval.
  const hasBuild = !!build
  useEffect(() => {
    // Poll only while a build is in flight. A compiled view is fetched once
    // more, for its platformio.ini, which the design response leaves out.
    if (!circuitId || !token || !hasBuild) return
    if (status !== 'compiling' && !needsIni) return
    let stopped = false
    let timer: ReturnType<typeof setInterval> | undefined
    const poll = async () => {
      try {
        const next = await getFirmware(circuitId, token)
        if (stopped) return
        setView(next)
        setPolled(next)
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
  }, [circuitId, token, hasBuild, status, needsIni])

  useEffect(() => {
    if (!polled) return
    // Only a state that differs from the last one reported: the page may hand it straight back as `build`.
    const key = `${polled.status}|${polled.build ?? ''}|${polled.firmware ? 1 : 0}|${polled.platformio_ini ? 1 : 0}`
    if (key === reported.current) return
    reported.current = key
    onBuildRef.current?.(polled)
  }, [polled])

  if (!view || view.status === 'none') {
    return (
      <SheetFrame>
        <EmptyState title="No firmware for this circuit type (passive circuits have no MCU code).">
          Firmware is generated only for a design with a microcontroller, and shown once it compiles.
        </EmptyState>
      </SheetFrame>
    )
  }

  if (view.status === 'unavailable') {
    // The build could not be run here (no toolchain): not a verdict on the firmware, so grey.
    return (
      <SheetFrame meta={view.board ? <span className="t-data">{view.board}</span> : undefined}>
        <EmptyState title="Firmware not available">{view.message}</EmptyState>
      </SheetFrame>
    )
  }

  const board = view.board ?? view.target ?? null

  if (view.status !== 'compiled' || !view.firmware) {
    const failed = view.status === 'failed'
    return (
      <SheetFrame meta={<>src/main.ino{board ? <> · <span className="t-data">{board}</span></> : null}</>}>
        <div className="flex flex-col gap-4 max-w-[110ch]">
          {failed ? (
            <Callout tone="fail" title="Build failed" role="alert">{view.message}</Callout>
          ) : (
            <p className="t-ui c-fg">
              <Cursor label={view.status === 'compiling' ? 'Compiling' : undefined} />{' '}
              {view.message}
            </p>
          )}
          {view.build && (
            <p className="t-small c-fg-3">
              Build <span className="t-data c-fg-2 break-all">{view.build}</span>
            </p>
          )}
          {failed && view.log && (
            <div className="flex flex-col gap-2">
              <span className="t-label">Build log · tail</span>
              <pre className="t-data c-fg-2 bg-bench-0 border border-line p-3 overflow-auto whitespace-pre">
                {view.log}
              </pre>
            </div>
          )}
        </div>
      </SheetFrame>
    )
  }

  const source = view.firmware
  const ini = view.platformio_ini ?? null
  const lineCount = source.split('\n').length
  // The labels stay in the accessible name on every width; below 720px only the icon shows.
  const narrowHide = 'max-[719.98px]:sr-only'
  return (
    <SheetFrame
      padded={false}
      scroll={false}
      meta={<>src/main.ino{view.board ? ` · compiled for the ${view.board}` : ''}</>}
      actions={
        <>
          <CopyButton value={source} label="firmware source" />
          {ini && (
            <Button size="sm" icon={<Download {...ICON} />} onClick={() => download('platformio.ini', ini)}>
              <span className={narrowHide}>Download platformio.ini</span>
            </Button>
          )}
          <Button size="sm" icon={<Download {...ICON} />} onClick={() => download('main.ino', source)}>
            <span className={narrowHide}>Download .ino</span>
          </Button>
        </>
      }
    >
      <div className="flex flex-col h-full">
        <div className="flex-1 min-h-0">
          <SourceView text={source} label="Firmware source, src/main.ino" />
        </div>
        <div className="flex-none flex items-center gap-4 h-[26px] px-4 border-t border-line bg-bench-1 t-small c-fg-3 min-w-0">
          <span><span className="t-data c-fg-2">{lineCount}</span> lines</span>
          {view.build && (
            <span className="truncate-1" title={view.build}>
              build <span className="t-data c-fg-2">{view.build}</span>
            </span>
          )}
        </div>
      </div>
    </SheetFrame>
  )
}
