'use client'

/**
 * Sheet 04 — Simulation. The ngspice job for this design, polled every 3 s
 * until it is complete or failed (the interval is cleared on unmount).
 */

import { useEffect, useState, useRef } from 'react'
import { pollSimulation, SimulationStatus } from '@/lib/api'
import WaveformChart, { siParts } from '@/components/WaveformChart'
import { Callout, Cursor, EmptyState, Qty, Section, SheetFrame } from '@/components/ui'

interface Props {
  circuitId: string | null
  jobId: string | null
  token: string
}

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`

export default function SimulationResults({ circuitId, jobId, token }: Props) {
  const [status, setStatus] = useState<SimulationStatus | null>(null)
  const [polling, setPolling] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!circuitId || !jobId || !token) return

    setStatus(null)
    setPolling(true)

    async function poll() {
      try {
        const s = await pollSimulation(circuitId!, jobId!, token)
        setStatus(s)
        if (s.status === 'complete' || s.status === 'failed') {
          clearInterval(intervalRef.current!)
          setPolling(false)
        }
      } catch {
        clearInterval(intervalRef.current!)
        setPolling(false)
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 3000)
    return () => clearInterval(intervalRef.current!)
  }, [circuitId, jobId, token])

  if (!jobId) {
    return (
      <SheetFrame meta="no job">
        <EmptyState title="No simulation for this design">
          No simulation started for this design.
        </EmptyState>
      </SheetFrame>
    )
  }

  if (!status || (status.status !== 'complete' && status.status !== 'failed')) {
    const running = status?.status === 'running'
    const word = running ? 'running' : 'queued'
    return (
      <SheetFrame meta={<span className="t-data">{word}{polling ? ' · polling every 3 s' : ''}</span>}>
        <div className="flex flex-col gap-2 py-6 max-w-[560px]" role="status">
          <p className="text-[15px] font-semibold text-fg flex items-baseline gap-2">
            <Cursor />
            {running ? 'Running — ngspice is simulating this design…' : 'Queued — waiting for simulation worker…'}
          </p>
          <p className="text-fg-2">
            {polling
              ? 'This sheet checks the job every 3 seconds and fills in when it completes.'
              : 'Polling stopped: the job could not be read. Open the sheet again to retry.'}
          </p>
        </div>
      </SheetFrame>
    )
  }

  const dcVoltages = status.results?.dc_voltages
  const waveforms = status.results?.waveforms
  const currents = waveforms?.dc.currents ?? {}
  const hasAc = !!waveforms && waveforms.ac.x.length > 1
  const hasTran = !!waveforms && waveforms.tran.x.length > 1
  const duration = status.duration_ms ? seconds(status.duration_ms) : null

  return (
    <SheetFrame meta={<span className="t-data">{status.status}{duration ? ` · ${duration}` : ''}</span>}>
      <div className="max-w-[1100px]">
        {status.status === 'failed' && (
          <Callout tone="fail" title="Simulation failed" role="alert" className="mb-8">
            {status.error
              ? <pre className="t-data text-fg whitespace-pre-wrap break-words">{status.error}</pre>
              : 'The worker reported a failure without an error message.'}
          </Callout>
        )}

        {status.grade && <VerdictSlab grade={status.grade} duration={duration} />}

        {status.status === 'complete' && status.error && (
          <Callout tone="fail" className="mt-4"><pre className="t-data whitespace-pre-wrap break-words">{status.error}</pre></Callout>
        )}

        {/* Waveforms (Stage 3). Results stored before Stage 3 carry none. */}
        {status.status === 'complete' && (
          <Section label="Waveforms" className="mt-8">
            {!waveforms ? (
              <p className="text-fg-2">
                This result was stored before waveform capture existed; re-run the simulation to plot it.
              </p>
            ) : !hasAc && !hasTran ? (
              <p className="text-fg-2">This simulation has no AC or transient sweep — the DC operating point is below.</p>
            ) : (
              <div className="flex flex-col gap-6">
                {hasAc && <WaveformChart title="AC sweep" sweep={waveforms.ac} logX xUnit="Hz" yUnit="V" />}
                {hasTran && <WaveformChart title="Transient" sweep={waveforms.tran} xUnit="s" yUnit="V" />}
              </div>
            )}
          </Section>
        )}

        {((dcVoltages && Object.keys(dcVoltages).length > 0) || Object.keys(currents).length > 0) && (
          <div className="grid gap-x-12 gap-y-8 mt-8 lg:grid-cols-2 items-start">
            {dcVoltages && Object.keys(dcVoltages).length > 0 && (
              <div>
                <Section label="DC operating point" count={Object.keys(dcVoltages).length}>
                  <table className="dt">
                    <thead>
                      <tr><th>Node</th><th className="num">Voltage</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(dcVoltages).map(([node, v]) => (
                        <tr key={node}>
                          <td className="mono">{node}</td>
                          <td className="num"><Qty value={v.toFixed(4)} unit="V" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              </div>
            )}

            {/* Source currents — a supply delivering current reads negative */}
            {Object.keys(currents).length > 0 && (
              <div>
                <Section label="Source currents" count={Object.keys(currents).length}>
                  <table className="dt">
                    <thead>
                      <tr><th>Source</th><th className="num">Current</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(currents).map(([source, amps]) => {
                        const [n, u] = siParts(amps, 'A')
                        return (
                          <tr key={source}>
                            <td className="mono">{source}</td>
                            <td className="num"><Qty value={n} unit={u} /></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  <p className="t-small text-fg-3 mt-2">A supply delivering current reads negative.</p>
                </Section>
              </div>
            )}
          </div>
        )}
      </div>
    </SheetFrame>
  )
}

function VerdictSlab({ grade, duration }: {
  grade: NonNullable<SimulationStatus['grade']>
  duration: string | null
}) {
  const pass = grade.passed
  return (
    <div>
      <div className={`flex flex-wrap items-end gap-x-6 gap-y-2 border px-5 py-4 ${
        pass ? 'border-pass bg-pass-bg text-pass' : 'border-fail bg-fail-bg text-fail'}`}>
        <div className="flex flex-col gap-2">
          <span className="t-label" style={{ color: 'inherit' }}>Simulation</span>
          <p className="flex items-baseline gap-3 leading-none">
            <span className="font-mono text-[32px] font-semibold" aria-hidden="true">{pass ? '✓' : '✕'}</span>
            <span className="text-[48px] font-semibold leading-none tracking-[-0.02em]" style={{ fontStretch: '75%' }}>
              {pass ? 'PASS' : 'FAIL'}
            </span>
            <span className="sr-only">{pass ? 'Simulation PASS' : 'Simulation FAIL'}</span>
          </p>
        </div>
        <div className="ml-auto flex flex-col items-end gap-2 text-right">
          {duration && <span className="t-data text-fg">{duration}</span>}
          <span className="t-small text-fg-2">
            {grade.failures.length > 0
              ? `${grade.failures.length} failure(s) reported by the grader`
              : 'no failures reported by the grader'}
          </span>
        </div>
      </div>

      {grade.failures.length > 0 && (
        <Callout tone="fail" title="Failures" className="mt-3">
          <ul className="flex flex-col gap-1">
            {grade.failures.map((f, i) => (
              <li key={i} className="t-data text-fg">✕ {f}</li>
            ))}
          </ul>
        </Callout>
      )}
      {grade.notes.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 text-fg-2">
          {grade.notes.map((n, i) => (
            <li key={i} className="flex gap-2"><span className="text-fg-3" aria-hidden="true">–</span>{n}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
