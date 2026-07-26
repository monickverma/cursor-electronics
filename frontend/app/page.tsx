'use client'

import dynamic from 'next/dynamic'
import { useState, useCallback } from 'react'
import ChatPanel from '@/components/ChatPanel'
import ValidationReport from '@/components/ValidationReport'
import FirmwareViewer from '@/components/FirmwareViewer'
import SimulationResults from '@/components/SimulationResults'
import BOMTable from '@/components/BOMTable'
import LandingPage from '@/components/LandingPage'
import PCBViewer from '@/components/PCBViewer'
import { GenerateResponse, PatchResponse } from '@/lib/api'

const SchematicViewer = dynamic(() => import('@/components/SchematicViewer'), { ssr: false })

type Tab = 'schematic' | 'pcb' | 'firmware' | 'simulation' | 'bom' | 'validation'

const TABS: { id: Tab; label: string }[] = [
  { id: 'schematic',  label: 'Schematic' },
  { id: 'pcb',        label: 'PCB' },
  { id: 'firmware',   label: 'Firmware' },
  { id: 'simulation', label: 'Simulation' },
  { id: 'bom',        label: 'BOM' },
  { id: 'validation', label: 'Validation' },
]

export default function Home() {
  const [result, setResult] = useState<GenerateResponse | PatchResponse | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('schematic')
  const [token, setToken] = useState<string>('')
  const [showApp, setShowApp] = useState(false)

  const handleResult = useCallback((res: GenerateResponse | PatchResponse) => {
    setResult(res)
    setActiveTab('schematic')
  }, [])

  const errorCount = result?.validation?.errors?.length ?? 0

  // Show marketing page until user explicitly clicks "Get started" or is already logged in
  if (!token && !showApp) {
    return <LandingPage onGetStarted={() => setShowApp(true)} />
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--lumen)' }}>

      {/* ── Left panel — cream / chat ───────────────────────── */}
      <div
        className="flex flex-col scroll-light"
        style={{
          width: 420,
          minWidth: 320,
          background: 'var(--lumen)',
          borderRight: '1px solid var(--border-light)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem 1rem',
            borderBottom: '1px solid var(--border-light)',
          }}
        >
          <h1
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'var(--h4)',
              color: 'var(--vast)',
              fontStyle: 'italic',
              letterSpacing: '-0.02em',
            }}
          >
            Circuit OS
          </h1>
          <p style={{ fontSize: 'var(--body-xs)', color: 'var(--text-muted-light)', marginTop: 2 }}>
            AI hardware compiler
          </p>
        </div>

        {/* Chat */}
        <ChatPanel
          onResult={handleResult}
          token={token}
          onTokenChange={setToken}
          currentCircuitId={(result as GenerateResponse)?.circuit_id}
        />
      </div>

      {/* ── Right panel — dark / output ─────────────────────── */}
      <div
        className="flex flex-col flex-1 min-w-0"
        style={{ background: 'var(--vast)' }}
      >
        {/* Tab bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'stretch',
            gap: 2,
            padding: '0 1.25rem',
            borderBottom: '1px solid var(--border-dark)',
            background: '#111',
            height: 44,
          }}
        >
          {TABS.map(tab => {
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={isActive ? 'tab-active' : ''}
                style={{
                  padding: '0 14px',
                  fontSize: 'var(--body-xs)',
                  fontFamily: 'var(--font-body)',
                  fontWeight: isActive ? 500 : 400,
                  color: isActive ? 'var(--lumen)' : 'var(--text-muted-dark)',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'color 0.15s',
                  position: 'relative',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.color = 'var(--lumen)' }}
                onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.color = 'var(--text-muted-dark)' }}
              >
                {tab.label}
                {tab.id === 'validation' && errorCount > 0 && (
                  <span
                    style={{
                      marginLeft: 5,
                      fontSize: 10,
                      background: '#7f1d1d',
                      color: '#fca5a5',
                      padding: '1px 5px',
                      borderRadius: 8,
                    }}
                  >
                    {errorCount}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* Output content */}
        <div className="flex-1 overflow-hidden">
          {!result ? (
            <EmptyState />
          ) : (
            <>
              {activeTab === 'schematic'  && <SchematicViewer schematic={result.schematic} />}
              {activeTab === 'pcb'        && <PCBViewer netlist={result.pcb_netlist} />}
              {activeTab === 'firmware'   && <FirmwareViewer firmware={result.firmware} />}
              {activeTab === 'simulation' && (
                <SimulationResults
                  circuitId={(result as GenerateResponse).circuit_id}
                  jobId={(result as GenerateResponse).simulation_job_id || null}
                  token={token}
                />
              )}
              {activeTab === 'bom'        && <BOMTable rows={(result as GenerateResponse).bom || []} />}
              {activeTab === 'validation' && (
                <ValidationReport
                  validation={result.validation}
                  explanation={(result as GenerateResponse).explanation}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div
      className="h-full flex items-center justify-center"
      style={{ background: 'var(--vast)' }}
    >
      <div style={{ textAlign: 'center', maxWidth: 380, padding: '0 2rem' }}>
        {/* Teal badge */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--fathom)',
            color: 'var(--lumen)',
            fontSize: 'var(--body-xs)',
            padding: '6px 14px',
            borderRadius: 100,
            marginBottom: '1.5rem',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            fontWeight: 500,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--glow)', display: 'inline-block' }} />
          Ready
        </div>

        <h2
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'var(--h3)',
            color: 'var(--lumen)',
            fontStyle: 'italic',
            marginBottom: '0.75rem',
          }}
        >
          Describe your circuit
        </h2>
        <p
          style={{
            fontSize: 'var(--body-sm)',
            color: 'var(--text-muted-dark)',
            lineHeight: 1.7,
            marginBottom: '2rem',
          }}
        >
          Type a description in the chat panel. Circuit OS generates a validated
          schematic, firmware, SPICE simulation, and BOM.
        </p>

        {/* Feature pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
          {['Schematic', 'Firmware', 'Simulation', 'BOM', 'Explanation'].map(f => (
            <span
              key={f}
              style={{
                fontSize: 'var(--body-xs)',
                color: 'var(--text-muted-dark)',
                border: '1px solid var(--border-dark)',
                borderRadius: 100,
                padding: '4px 12px',
              }}
            >
              {f}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
