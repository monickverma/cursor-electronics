// v3 — the flow desktop: the requirement as the headline, each output a window on live water
'use client'

import { useState, useCallback, useEffect, ReactNode } from 'react'
import ChatPanel from '@/components/ChatPanel'
import ValidationReport from '@/components/ValidationReport'
import FirmwareViewer from '@/components/FirmwareViewer'
import SimulationResults from '@/components/SimulationResults'
import BOMTable from '@/components/BOMTable'
import LandingPage from '@/components/LandingPage'
import PCBViewer from '@/components/PCBViewer'
import FlowBackground from '@/components/FlowBackground'
import FloatWindow from '@/components/FloatWindow'
import SchematicPanel from '@/components/SchematicPanel'
import PartsSheet from '@/components/PartsSheet'
import Library from '@/components/Library'
import type { Message } from '@/components/ChatPanel'
import {
  GenerateResponse, PatchResponse, ValidationCoverage, fetchHealth,
  getHistory, openDesign, whoAmI, type DesignHistory, type DesignView,
} from '@/lib/api'
import { DEMO_MODE, REPO_URL } from '@/lib/demo'

const TOKEN_KEY = 'circuitos.token'
const LIBRARY_KEY = 'circuitos.library'

// Storage can be blocked (private windows, site-data settings): the app then
// works exactly as before, it just does not remember the session.
function readStored(key: string): string | null {
  try { return window.localStorage.getItem(key) } catch { return null }
}
function writeStored(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch { /* not remembered */ }
}

/**
 * The conversation behind a saved design, rebuilt from what was stored: the
 * requirement as recorded, then each change that was asked for and what it did.
 * The model's own first reply is not stored, so it is not invented here.
 */
function conversationOf(view: DesignView, history: DesignHistory | null): Message[] {
  const at = (iso: string | null) => (iso ? new Date(iso) : new Date())
  const messages: Message[] = [{ role: 'user', text: view.intent, timestamp: at(view.created_at) }]
  for (const entry of history?.entries ?? []) {
    const changes = Array.isArray(entry.changes) ? entry.changes.filter(c => typeof c === 'string') : []
    messages.push({
      role: 'user',
      text: entry.prompted_by || 'A change made from the parts list',
      timestamp: at(entry.created_at),
    })
    messages.push({
      role: 'assistant',
      text: `Requirement changed${changes.length ? ` — ${changes.join('; ')}` : ''}. Design became v${entry.to_version}.`
        + (entry.predict_delta?.length ? `\n\nPredicted: ${entry.predict_delta.join('; ')}` : ''),
      timestamp: at(entry.created_at),
    })
  }
  messages.push({
    role: 'assistant',
    text: `Opened from your library at v${view.version}. ${view.patchable
      ? 'Ask for a change to carry on from here.'
      : 'It was saved before requirements were stored, so it can be read but not changed.'}`,
    timestamp: at(view.updated_at),
  })
  return messages
}

type Tab = 'schematic' | 'pcb' | 'firmware' | 'simulation' | 'bom' | 'validation' | 'parts'

// `label` is the dock button, and the name the UI tests open an output by.
const OUTPUTS: { id: Tab; label: string; title: string; column: 'left' | 'right'; height: number; tone?: 'screen' }[] = [
  // The board in 3D comes first, on the owner's instruction (2026-11-15): first in the
  // dock, open when a design arrives, and the largest window. Still experimental.
  { id: 'pcb',        label: 'PCB (experimental)', title: 'Board in 3D (experimental)', column: 'left',  height: 640, tone: 'screen' },
  { id: 'schematic',  label: 'Schematic',          title: 'Schematic',            column: 'left',  height: 580 },
  { id: 'firmware',   label: 'Firmware',           title: 'Firmware',             column: 'right', height: 400 },
  { id: 'simulation', label: 'Simulation',         title: 'Simulation',           column: 'left',  height: 440 },
  { id: 'bom',        label: 'BOM',                title: 'Bill of materials',    column: 'right', height: 460 },
  { id: 'validation', label: 'Validation',         title: 'Claims and checks',    column: 'right', height: 640 },
  { id: 'parts',      label: 'Parts',              title: 'Parts sheet',          column: 'left',  height: 560 },
]

// What is on the desktop when a design arrives: the board (where the engine is on),
// the schematic and the claims. The rest open from the dock, so nothing polls or
// fetches (simulation, firmware build, BOM prices) unasked.
const OPEN_AT_START: Record<Tab, boolean> = {
  pcb: true, schematic: true, validation: true, firmware: false, simulation: false, bom: false, parts: false,
}

export default function Home() {
  const [result, setResult] = useState<GenerateResponse | PatchResponse | null>(null)
  // The requirement as recorded, shown as the headline. A patch changes the
  // requirement but its response carries no sentence, so the first one stays.
  const [requirement, setRequirement] = useState('')
  const [open, setOpen] = useState<Record<Tab, boolean>>(OPEN_AT_START)
  const [focus, setFocus] = useState<Record<Tab, number>>({
    schematic: 0, validation: 0, pcb: 0, firmware: 0, simulation: 0, bom: 0, parts: 0,
  })
  const [token, setToken] = useState<string>('')
  const [showApp, setShowApp] = useState(false)

  // ── The session and the library ──────────────────────────────────────────
  // The token is kept in this browser so a reload does not sign the person out
  // (amended 2026-11-16; it used to live in memory only). It is checked against
  // /auth/me before it is trusted, and dropped if the backend refuses it.
  const [restoring, setRestoring] = useState(true)
  const [email, setEmail] = useState<string | undefined>(undefined)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [libraryVersion, setLibraryVersion] = useState(0)
  const [thread, setThread] = useState<{ key: string; messages: Message[] }>({ key: 'new', messages: [] })
  const [openError, setOpenError] = useState('')
  const [seed, setSeed] = useState('')

  useEffect(() => {
    if (DEMO_MODE) { setRestoring(false); return }
    let cancelled = false
    const stored = readStored(TOKEN_KEY)
    setLibraryOpen(readStored(LIBRARY_KEY) !== '0' && window.innerWidth >= 1100)
    if (!stored) { setRestoring(false); return }
    whoAmI(stored)
      .then(me => {
        if (cancelled) return
        setToken(stored)
        setEmail(me.email)
        setShowApp(true)
      })
      .catch(() => writeStored(TOKEN_KEY, null))
      .finally(() => { if (!cancelled) setRestoring(false) })
    return () => { cancelled = true }
  }, [])

  const signedIn = useCallback((t: string) => {
    setToken(t)
    if (DEMO_MODE || !t) return
    writeStored(TOKEN_KEY, t)
    whoAmI(t).then(me => setEmail(me.email)).catch(() => {})
  }, [])

  const newDesign = useCallback(() => {
    setResult(null)
    setRequirement('')
    setOpenError('')
    setOpen(OPEN_AT_START)
    setThread({ key: `new:${Date.now()}`, messages: [] })
    window.scrollTo({ top: 0 })
  }, [])

  const signOut = useCallback(() => {
    writeStored(TOKEN_KEY, null)
    setToken('')
    setEmail(undefined)
    setShowApp(false)
    setResult(null)
    setRequirement('')
    setThread({ key: `new:${Date.now()}`, messages: [] })
  }, [])

  const toggleLibrary = useCallback(() => {
    setLibraryOpen(o => {
      writeStored(LIBRARY_KEY, o ? '0' : '1')
      return !o
    })
  }, [])

  // Open a saved design: the design re-derived from its stored IR, and the
  // conversation rebuilt from the requirement and its patch history.
  const openSaved = useCallback(async (circuitId: string) => {
    setOpenError('')
    try {
      const [view, history] = await Promise.all([
        openDesign(circuitId, token),
        getHistory(circuitId, token).catch(() => null),
      ])
      setResult(view)
      setRequirement(view.intent)
      setOpen(OPEN_AT_START)
      setThread({ key: `${circuitId}:${Date.now()}`, messages: conversationOf(view, history) })
      if (window.innerWidth < 1100) setLibraryOpen(false)
      window.scrollTo({ top: 0 })
    } catch (e) {
      setOpenError(e instanceof Error ? e.message : 'That design could not be opened.')
    }
  }, [token])

  // The PCB engine is experimental and off in production, where /pcb/compile
  // returns 501. Ask the backend which build this is rather than rendering a
  // button whose every click is an error. Starts false so the button never
  // flashes in before the answer arrives, and stays false if /health is
  // unreachable — an unreachable backend is the same dead click as a disabled route.
  const [pcbEnabled, setPcbEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then(h => { if (!cancelled) setPcbEnabled(h.pcb_engine_enabled) })
      .catch(() => { if (!cancelled) setPcbEnabled(false) })
    return () => { cancelled = true }
  }, [])

  const outputs = OUTPUTS.filter(o => o.id !== 'pcb' || pcbEnabled)

  const handleResult = useCallback((res: GenerateResponse | PatchResponse) => {
    setResult(res)
    const intent = (res as GenerateResponse).intent
    if (intent) setRequirement(intent)
    setOpen(o => ({ ...o, schematic: true }))
    setLibraryVersion(n => n + 1)
  }, [])

  // A substitute from the BOM window is a patch: take the new revision, change nothing else.
  const handleBomPatched = useCallback((res: PatchResponse) => {
    setResult(res)
    setLibraryVersion(n => n + 1)
  }, [])

  // Sign-off changes what is claimed, never the design: only the coverage moves.
  const handleCoverage = useCallback((coverage: ValidationCoverage) => {
    setResult(r => (r ? { ...r, validation_coverage: coverage } : r))
  }, [])

  // A dock button opens its window and brings it forward. It never closes one:
  // a window is hidden from its own title bar.
  const show = useCallback((id: Tab) => {
    setOpen(o => ({ ...o, [id]: true }))
    setFocus(f => ({ ...f, [id]: f[id] + 1 }))
  }, [])
  const hide = useCallback((id: Tab) => {
    setOpen(o => ({ ...o, [id]: false }))
  }, [])

  const errorCount = result?.validation?.errors?.length ?? 0

  // While a stored session is being checked, show the ground and nothing else:
  // neither the landing page nor the sign-in window should flash past.
  if (restoring) return <div className="flow-app" aria-busy="true" />

  // Show marketing page until user explicitly clicks "Get started" or is already logged in
  if (!token && !showApp) {
    // Demo mode has no accounts to sign in to: straight to the examples.
    return (
      <LandingPage
        onGetStarted={prompt => {
          // A template on the front page hands over its request, ready to send.
          // (Demo mode opens recordings by exact prompt, so it takes none.)
          if (prompt && !DEMO_MODE) setSeed(prompt)
          setShowApp(true)
          if (DEMO_MODE) setToken('demo')
        }}
      />
    )
  }

  const hasLibrary = !!token && !DEMO_MODE

  function body(id: Tab): ReactNode {
    if (!result) return null
    switch (id) {
      case 'schematic':
        return (
          <SchematicPanel
            schematic={result.schematic}
            ir={result.ir}
            findings={[...(result.validation?.errors ?? []), ...(result.validation?.warnings ?? [])]}
          />
        )
      case 'pcb':
        return <PCBViewer netlist={result.pcb_netlist} token={token} />
      case 'firmware':
        return (
          <FirmwareViewer
            circuitId={result.circuit_id}
            token={token}
            firmware={result.firmware}
            build={result.firmware_build}
          />
        )
      case 'simulation':
        return (
          <SimulationResults
            circuitId={(result as GenerateResponse).circuit_id}
            jobId={(result as GenerateResponse).simulation_job_id || null}
            token={token}
          />
        )
      case 'bom':
        return (
          <BOMTable
            rows={(result as GenerateResponse).bom || []}
            circuitId={result.circuit_id}
            version={(result as PatchResponse).version}
            token={token}
            onPatched={handleBomPatched}
          />
        )
      case 'parts':
        return (
          <PartsSheet
            ir={result.ir}
            token={token}
            onAsk={request => { setSeed(request); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
          />
        )
      case 'validation':
        return (
          <ValidationReport
            validation={result.validation}
            coverage={result.validation_coverage}
            explanation={(result as GenerateResponse).explanation}
            explanationError={(result as GenerateResponse).explanation_error}
            explanationStatus={(result as GenerateResponse).explanation_status}
            circuitId={result.circuit_id}
            token={token}
            onCoverage={handleCoverage}
          />
        )
    }
  }

  function meta(id: Tab): string | undefined {
    if (!result) return undefined
    if (id === 'schematic') return `v${result.version}`
    if (id === 'validation') {
      const floor = result.validation_coverage?.grade_floor
      return floor ? `floor ${floor}` : undefined
    }
    return undefined
  }

  const column = (side: 'left' | 'right') => outputs.filter(o => o.column === side && open[o.id])
  const left = column('left')
  const right = column('right')

  const headline = requirement || 'Describe Your Circuit'
  // Before there is a design the headline is the page. Once there is one, the
  // windows are, so the top folds down and they start within the first screen.
  const sizes = result
    ? ['clamp(24px, 3vw, 42px)', 'clamp(20px, 2.2vw, 32px)', 'clamp(17px, 1.7vw, 24px)']
    : ['clamp(38px, 6vw, 84px)', 'clamp(30px, 4.2vw, 56px)', 'clamp(24px, 3vw, 40px)']
  const headlineSize = sizes[headline.length <= 60 ? 0 : headline.length <= 130 ? 1 : 2]

  return (
    <div className="flow-app">
      <FlowBackground />

      {hasLibrary && (
        <Library
          token={token}
          email={email}
          activeId={result?.circuit_id}
          refreshKey={libraryVersion}
          open={libraryOpen}
          onToggle={toggleLibrary}
          onOpenDesign={openSaved}
          onNewDesign={newDesign}
          onSignOut={signOut}
        />
      )}

      <div className={`desk relative z-10 flex flex-col min-h-screen ${hasLibrary && libraryOpen ? 'min-[1100px]:pl-[288px]' : ''}`}>
        <header className="flex flex-wrap items-stretch justify-between gap-2 min-h-[44px]">
          <span className={`flex items-center min-h-[44px] px-3.5 bg-paper text-ink font-pixel text-2xl tracking-wider ${
            hasLibrary && libraryOpen ? 'min-[1100px]:invisible' : ''}`}>
            CIRCUIT OS
          </span>
          {DEMO_MODE && (
            <span className="flex items-center min-h-[44px] px-3.5 border-[1.5px] border-paper text-paper text-xs">
              Demo mode — recorded results
            </span>
          )}
        </header>

        <section className={`flex flex-col items-center px-6 text-center ${result ? 'gap-3 pt-3 pb-4' : 'gap-5 pt-10 pb-7'}`}>
          <p className={result ? 'text-xs' : 'text-sm'}>
            {result ? `version ${result.version} ...... you asked for` : 'AI hardware compiler'}
          </p>
          <h1 className="flow-headline max-w-[1180px]" style={{ fontSize: headlineSize }}>
            {headline}
          </h1>
          {!result && (
            <p className="max-w-[60ch] text-sm">
              {DEMO_MODE
                ? 'Pick an example below to open its recorded schematic, firmware, SPICE simulation, BOM and validation.'
                : 'Type a description below. Circuit OS generates a validated schematic, firmware, SPICE simulation, and BOM.'}
            </p>
          )}

          {DEMO_MODE && !result && <DemoBadge />}

          {openError && (
            <p role="alert" className="paper max-w-[760px] px-4 py-2 border-[1.5px] border-ink text-sm text-bad">
              {openError}
            </p>
          )}

          <ChatPanel
            onResult={handleResult}
            token={token}
            onTokenChange={signedIn}
            currentCircuitId={(result as GenerateResponse)?.circuit_id}
            threadKey={thread.key}
            initialMessages={thread.messages}
            seedPrompt={seed}
          />
        </section>

        {result && (
          <>
            <nav aria-label="Outputs" className="flex flex-wrap justify-center gap-2 px-6 pb-5">
              {outputs.map(o => (
                <button
                  key={o.id}
                  type="button"
                  className="flow-btn"
                  aria-pressed={open[o.id]}
                  onClick={() => show(o.id)}
                >
                  {o.label}
                  {o.id === 'validation' && errorCount > 0 && (
                    <span className="ml-2 px-1.5 py-px bg-[#b3261e] text-paper font-mono text-xs">
                      {errorCount}
                    </span>
                  )}
                </button>
              ))}
            </nav>

            <div className="flex flex-wrap items-start gap-7 px-6 pb-20">
              {left.length > 0 && (
                <div className="flex-[7_1_520px] min-w-0 flex flex-col gap-7">
                  {left.map(o => (
                    <FloatWindow key={o.id} id={o.id} title={o.title} meta={meta(o.id)} tone={o.tone}
                                 height={o.height} focusKey={focus[o.id]} onHide={() => hide(o.id)} maximizable>
                      {body(o.id)}
                    </FloatWindow>
                  ))}
                </div>
              )}
              {right.length > 0 && (
                <div className="flex-[5_1_420px] min-w-0 flex flex-col gap-7">
                  {right.map(o => (
                    <FloatWindow key={o.id} id={o.id} title={o.title} meta={meta(o.id)} tone={o.tone}
                                 height={o.height} focusKey={focus[o.id]} onHide={() => hide(o.id)} maximizable>
                      {body(o.id)}
                    </FloatWindow>
                  ))}
                </div>
              )}
              {left.length === 0 && right.length === 0 && (
                <p className="w-full text-center text-sm">Every window is hidden. Open one from the row above.</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function DemoBadge() {
  return (
    <div role="status" className="paper max-w-[760px] px-4 py-3 border-[1.5px] border-ink text-left text-sm leading-relaxed">
      <strong className="font-semibold">Demo mode — recorded results.</strong>{' '}
      No backend is attached to this deployment. The examples below are real outputs of the
      deterministic pipeline (generator, ngspice, PlatformIO, BOM), recorded locally; the
      requirement was entered through the form, not the LLM.{' '}
      <a href={`${REPO_URL}#readme`} target="_blank" rel="noopener noreferrer" className="underline">
        Run it locally
      </a>{' '}
      to describe your own circuit.
    </div>
  )
}
