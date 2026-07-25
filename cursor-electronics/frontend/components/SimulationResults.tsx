'use client'

import { useEffect, useState, useRef } from 'react'
import { pollSimulation, SimulationStatus } from '@/lib/api'

interface Props {
  circuitId: string | null
  jobId: string | null
  token: string
}

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
      <div className="h-full flex items-center justify-center text-muted text-sm">
        No simulation started for this design.
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

  const dcVoltages = status.results?.dc_voltages as Record<string, number> | undefined

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
        <div className={`rounded border p-4 ${status.grade.passed ? 'border-green-700 bg-green-900/20' : 'border-red-700 bg-red-900/20'}`}>
          <p className={`text-sm font-medium mb-2 ${status.grade.passed ? 'text-green-400' : 'text-red-400'}`}>
            {status.grade.passed ? '✓ Simulation PASS' : '✗ Simulation FAIL'}
          </p>
          {status.grade.failures.length > 0 && (
            <ul className="space-y-1">
              {status.grade.failures.map((f, i) => (
                <li key={i} className="text-xs text-red-300">• {f}</li>
              ))}
            </ul>
          )}
          {status.grade.notes.map((n, i) => (
            <p key={i} className="text-xs text-muted mt-1">{n}</p>
          ))}
        </div>
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

      {/* Error */}
      {status.error && (
        <div className="rounded border border-red-800 bg-red-900/20 p-3">
          <p className="text-xs text-red-300 font-mono">{status.error}</p>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    queued:   { label: 'Queued',    cls: 'bg-amber-900/30 text-amber-300 border-amber-700' },
    running:  { label: 'Running',   cls: 'bg-blue-900/30 text-blue-300 border-blue-700' },
    complete: { label: 'Complete',  cls: 'bg-green-900/30 text-green-300 border-green-700' },
    failed:   { label: 'Failed',    cls: 'bg-red-900/30 text-red-300 border-red-700' },
  }
  const s = map[status] || { label: status, cls: 'bg-surface text-muted border-border' }
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${s.cls}`}>{s.label}</span>
  )
}
