'use client'

import { useEffect, useState } from 'react'

interface Props {
  netlist?: Record<string, any>
}

interface PCBResponse {
  svg?: string
  stats?: {
    name?: string
    size_mm?: [number, number]
    components?: number
    pads?: number
    nets?: number
    connections?: number
    routed?: number
    unrouted?: number
    drc_errors?: number
    vias?: number
    copper_mm?: number
  }
  warnings?: string[]
  violations?: string[]
  error?: string
}

const PCB_SERVER_URL = process.env.NEXT_PUBLIC_PCB_SERVER_URL || 'http://localhost:8001/'

export default function PCBViewer({ netlist }: Props) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<PCBResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!netlist) return

    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(PCB_SERVER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(netlist),
    })
      .then(async (res) => {
        if (cancelled) return
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.error || `HTTP ${res.status} ${res.statusText}`)
        }
        return res.json()
      })
      .then((resData: PCBResponse) => {
        if (cancelled) return
        if (resData.error) {
          setError(resData.error)
        } else {
          setData(resData)
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'Failed to connect to PCB engine server.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [netlist])

  if (!netlist) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        No PCB netlist generated yet.
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col min-h-0" style={{ background: 'var(--vast)' }}>
      {/* Top Header / Stats Bar */}
      {data?.stats && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '1.25rem',
            padding: '0.75rem 1.25rem',
            background: '#111111',
            borderBottom: '1px solid var(--border-dark)',
            fontSize: 'var(--body-xs)',
            color: 'var(--lumen-dim)',
          }}
        >
          <div>
            <span style={{ color: 'var(--text-muted-dark)', marginRight: 4 }}>Board:</span>
            <strong style={{ color: 'var(--lumen)' }}>{data.stats.name}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted-dark)', marginRight: 4 }}>Dimensions:</span>
            <span>{data.stats.size_mm?.[0]} &times; {data.stats.size_mm?.[1]} mm</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted-dark)', marginRight: 4 }}>Routed:</span>
            <span style={{ color: data.stats.unrouted === 0 ? '#4ade80' : '#f87171' }}>
              {data.stats.routed}/{data.stats.connections}
            </span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted-dark)', marginRight: 4 }}>DRC Errors:</span>
            <span style={{ color: data.stats.drc_errors === 0 ? '#4ade80' : '#ef4444' }}>
              {data.stats.drc_errors}
            </span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted-dark)', marginRight: 4 }}>Vias:</span>
            <span>{data.stats.vias}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted-dark)', marginRight: 4 }}>Copper:</span>
            <span>{data.stats.copper_mm} mm</span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col items-center justify-center relative overflow-auto p-4">
        {loading && (
          <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--glow)' }}>
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            Compiling PCB layout...
          </div>
        )}

        {error && !loading && (
          <div
            style={{
              maxWidth: 480,
              padding: '1.5rem',
              borderRadius: 'var(--r-md)',
              background: '#281515',
              border: '1px solid #7f1d1d',
              color: '#fca5a5',
              textAlign: 'center',
            }}
          >
            <h3 style={{ fontSize: 'var(--h5)', marginBottom: '0.5rem', color: '#f87171' }}>
              PCB Engine Unavailable
            </h3>
            <p style={{ fontSize: 'var(--body-xs)', lineHeight: 1.6, marginBottom: '1rem', color: '#fecaca' }}>
              {error}
            </p>
            <div
              style={{
                background: '#120808',
                padding: '0.75rem',
                borderRadius: 'var(--r-sm)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.75rem',
                color: 'var(--lumen)',
                textAlign: 'left',
              }}
            >
              python compile_board.py --serve 8001
            </div>
          </div>
        )}

        {data?.svg && !loading && (
          <div
            id="pcb-panel"
            className="w-full h-full flex items-center justify-center overflow-auto"
            dangerouslySetInnerHTML={{ __html: data.svg }}
          />
        )}
      </div>

      {/* Warnings footer */}
      {data?.warnings && data.warnings.length > 0 && (
        <details className="border-t border-border-dark" style={{ background: '#141414' }}>
          <summary className="px-4 py-2 text-xs text-amber-400 cursor-pointer hover:text-amber-300 select-none">
            PCB Engine Warnings ({data.warnings.length})
          </summary>
          <ul className="px-6 py-2 text-xs font-mono text-amber-200 list-disc space-y-1 max-h-32 overflow-auto">
            {data.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
