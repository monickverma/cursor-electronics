'use client'

import { useEffect, useState, useRef } from 'react'
import { DEMO_MODE, pollSimulation, startSimulation, SimulationStatus } from '@/lib/api'
import WaveformChart, { si } from '@/components/WaveformChart'

interface Props {
  circuitId: string | null
  jobId: string | null
  token: string
}

export default function SimulationResults({ circuitId, jobId: givenJob, token }: Props) {
  // A design opened from the library arrives without a job: its last run is not
  // kept. The person can queue a fresh one from here.
  const [ownJob, setOwnJob] = useState<string | null>(null)
  const [startError, setStartError] = useState('')
  const [starting, setStarting] = useState(false)
  useEffect(() => { setOwnJob(null); setStartError('') }, [circuitId, givenJob])
  const jobId = givenJob ?? ownJob

  async function runNow() {
    if (!circuitId || !token || starting) return
    setStarting(true)
    setStartError('')
    try {
      setOwnJob((await startSimulation(circuitId, token)).job_id)
    } catch (e) {
      setStartError(e instanceof Error ? e.message : 'The simulation could not be queued.')
    } finally {
      setStarting(false)
    }
  }

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
      <div className="h-full flex flex-col items-center justify-center gap-3 p-5 text-center text-muted text-sm">
        <p>No simulation started for this design.</p>
        {circuitId && token && !DEMO_MODE && (
          <button type="button" onClick={runNow} disabled={starting}
                  className="min-h-[44px] px-4 bg-lavender text-dark font-medium disabled:opacity-60">
            {starting ? 'Queuing…' : 'Run the simulation'}
          </button>
        )}
        {startError && <p className="text-bad">{startError}</p>}
      </div>
    )
  }

  if (!status || (polling && !status)) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="w-6 h-6 border-2 border-lavender border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-muted">Queued — waiting for simulation worker…</p>
        </div>
      </div>
    )
  }

  const dcVoltages = status.results?.dc_voltages
  const waveforms = status.results?.waveforms
  const currents = waveforms?.dc.currents ?? {}

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* Status badge */}
      <div className="flex items-center gap-3">
        <StatusBadge status={status.status} />
        {status.duration_ms && (
          <span className="text-xs text-muted">{(status.duration_ms / 1000).toFixed(1)}s</span>
        )}
        {polling && <div className="w-3 h-3 border border-lavender border-t-transparent rounded-full animate-spin" />}
      </div>

      {/* Grade */}
      {status.grade && (
        <div className={`rounded border p-4 ${status.grade.passed ? 'border-ok bg-ok/10' : 'border-bad bg-bad/10'}`}>
          <p className={`text-sm font-medium mb-2 ${status.grade.passed ? 'text-ok' : 'text-bad'}`}>
            {status.grade.passed ? '✓ Simulation PASS' : '✗ Simulation FAIL'}
          </p>
          {status.grade.failures.length > 0 && (
            <ul className="space-y-1">
              {status.grade.failures.map((f, i) => (
                <li key={i} className="text-xs text-bad">• {f}</li>
              ))}
            </ul>
          )}
          {status.grade.notes.map((n, i) => (
            <p key={i} className="text-xs text-muted mt-1">{n}</p>
          ))}
        </div>
      )}

      {/* Waveforms (Stage 3). Results stored before Stage 3 carry none. */}
      {status.status === 'complete' && !waveforms && (
        <p className="text-xs text-muted">
          This result was stored before waveform capture existed; re-run the simulation to plot it.
        </p>
      )}
      {waveforms && waveforms.ac.x.length > 1 && (
        <WaveformChart title="AC sweep" sweep={waveforms.ac} logX xUnit="Hz" yUnit="V" />
      )}
      {waveforms && waveforms.tran.x.length > 1 && (
        <WaveformChart title="Transient" sweep={waveforms.tran} xUnit="s" yUnit="V" />
      )}

      {/* DC voltages */}
      {dcVoltages && Object.keys(dcVoltages).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-cream mb-2">DC Operating Point</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-1 pr-4 text-muted font-normal">Node</th>
                <th className="text-right py-1 text-muted font-normal">Voltage</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(dcVoltages).map(([node, v]) => (
                <tr key={node} className="border-b border-border/50">
                  <td className="py-1.5 pr-4 font-mono text-xs text-cream-dim">{node}</td>
                  <td className="py-1.5 text-right font-mono text-xs text-lavender">{v.toFixed(4)} V</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Source currents — a supply delivering current reads negative */}
      {Object.keys(currents).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-cream mb-2">Source currents</h3>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(currents).map(([source, amps]) => (
                <tr key={source} className="border-b border-border/50">
                  <td className="py-1.5 pr-4 font-mono text-xs text-cream-dim">{source}</td>
                  <td className="py-1.5 text-right font-mono text-xs text-lavender">{si(amps, 'A')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Error */}
      {status.error && (
        <div className="rounded border border-bad bg-bad/10 p-3">
          <p className="text-xs text-bad font-mono">{status.error}</p>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    queued:   { label: 'Queued',    cls: 'bg-warn/10 text-warn border-warn' },
    running:  { label: 'Running',   cls: 'bg-info/10 text-info border-info' },
    complete: { label: 'Complete',  cls: 'bg-ok/10 text-ok border-ok' },
    failed:   { label: 'Failed',    cls: 'bg-bad/10 text-bad border-bad' },
  }
  const s = map[status] || { label: status, cls: 'bg-surface text-muted border-border' }
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${s.cls}`}>{s.label}</span>
  )
}
