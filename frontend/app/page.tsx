// v3 — the workbench: numbered sheets, title block, requirement panel (spec 2026-11-13 §5)
'use client'

import dynamic from 'next/dynamic'
import { useState, useCallback, useEffect } from 'react'
import ChatPanel from '@/components/ChatPanel'
import ValidationReport from '@/components/ValidationReport'
import FirmwareViewer from '@/components/FirmwareViewer'
import SimulationResults from '@/components/SimulationResults'
import BOMTable from '@/components/BOMTable'
import LandingPage from '@/components/LandingPage'
import PCBViewer from '@/components/PCBViewer'
import {
  AuthFrame, DemoNotice, EmptySheet, OverviewSheet, RequirementPanel, SHEETS, SheetHost, SheetTabs,
  StatusBar, TopBar, Workbench, designFacts, useMediaQuery, useWorkbenchShortcuts,
  BP_COMPACT, BP_DRAWER, SHEET_BY_ID, type SheetId,
} from '@/components/workbench'
import { FirmwareBuild, GenerateResponse, PatchResponse, ValidationCoverage, fetchHealth } from '@/lib/api'
import { DEMO_MODE, REPO_URL } from '@/lib/demo'

const SchematicViewer = dynamic(() => import('@/components/SchematicViewer'), { ssr: false })

type Tab = SheetId

const PANEL_ID = 'requirement-panel'

export default function Home() {
  const [result, setResult] = useState<GenerateResponse | PatchResponse | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [token, setToken] = useState<string>('')
  const [showApp, setShowApp] = useState(false)
  // The wordmark returns to the landing page without discarding the session or the design.
  const [atLanding, setAtLanding] = useState(false)
  const [panelOpen, setPanelOpen] = useState(true)

  const drawer = useMediaQuery(BP_DRAWER)
  const compact = useMediaQuery(BP_COMPACT)

  // The PCB engine is experimental and off in production, where /pcb/compile
  // returns 501. Ask the backend which build this is rather than rendering a
  // tab whose every click is an error. Starts false so the tab never flashes
  // in before the answer arrives, and stays false if /health is unreachable —
  // an unreachable backend is the same dead click as a disabled route.
  const [pcbEnabled, setPcbEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then(h => { if (!cancelled) setPcbEnabled(h.pcb_engine_enabled) })
      .catch(() => { if (!cancelled) setPcbEnabled(false) })
    return () => { cancelled = true }
  }, [])

  const visibleTabs = SHEETS.filter(t => t.id !== 'pcb' || pcbEnabled)

  // If the engine is disabled while the PCB tab is somehow selected (it is the
  // initial tab for nobody, but a stale state or a future default could get
  // here), fall back rather than render a panel with no tab.
  useEffect(() => {
    if (!pcbEnabled && activeTab === 'pcb') setActiveTab('overview')
  }, [pcbEnabled, activeTab])

  // A new design or revision opens on the Overview sheet: the compile report.
  // In the drawer layout the drawer closes so the report is visible.
  const handleResult = useCallback((res: GenerateResponse | PatchResponse) => {
    setResult(res)
    setActiveTab('overview')
    if (drawer) setPanelOpen(false)
  }, [drawer])

  // A substitute from the BOM tab is a patch: take the new revision, stay on the tab.
  const handleBomPatched = useCallback((res: PatchResponse) => {
    setResult(res)
  }, [])

  // Sign-off changes what is claimed, never the design: only the coverage moves.
  const handleCoverage = useCallback((coverage: ValidationCoverage) => {
    setResult(r => (r ? { ...r, validation_coverage: coverage } : r))
  }, [])

  // The firmware sheet polls the compile gate; what it learns is the design's build state,
  // so the status bar and the Overview stop saying "compiling" once it has compiled.
  const handleFirmwareBuild = useCallback((build: FirmwareBuild) => {
    setResult(r => (r ? { ...r, firmware_build: build, firmware: build.firmware ?? r.firmware } : r))
  }, [])

  const togglePanel = useCallback(() => setPanelOpen(o => !o), [])
  const closePanel = useCallback(() => setPanelOpen(false), [])
  const openSheetNumber = useCallback((n: number) => {
    const sheet = SHEETS.find(s => Number(s.number) === n)
    if (sheet && (sheet.id !== 'pcb' || pcbEnabled)) setActiveTab(sheet.id)
  }, [pcbEnabled])

  const goHome = useCallback(() => setAtLanding(true), [])
  const signOut = useCallback(() => {
    setToken('')
    setResult(null)
    setActiveTab('overview')
    setAtLanding(false)
    setShowApp(false)
  }, [])

  const inWorkbench = !atLanding && (!!token || showApp)
  useWorkbenchShortcuts(inWorkbench && !!token, togglePanel, openSheetNumber)

  const errorCount = result?.validation?.errors?.length ?? 0
  const facts = result ? designFacts(result) : null

  // Show marketing page until user explicitly clicks "Get started" or is already logged in
  if ((!token && !showApp) || atLanding) {
    // Demo mode has no accounts to sign in to: straight to the examples.
    return (
      <LandingPage
        onGetStarted={() => {
          setAtLanding(false)
          setShowApp(true)
          if (DEMO_MODE && !token) setToken('demo')
        }}
      />
    )
  }

  const chat = (
    <ChatPanel
      onResult={handleResult}
      token={token}
      onTokenChange={setToken}
      currentCircuitId={(result as GenerateResponse)?.circuit_id}
    />
  )

  // Live mode, no session yet: the sign-in panel, in the workbench frame.
  if (!token) {
    return (
      <Workbench
        top={<TopBar facts={null} demo={DEMO_MODE} repoUrl={REPO_URL} onHome={goHome} compact={compact} drawer={drawer} />}
        status={<StatusBar facts={null} demo={DEMO_MODE} />}
      >
        <AuthFrame>{chat}</AuthFrame>
      </Workbench>
    )
  }

  const sheet = SHEET_BY_ID[activeTab]

  return (
    <Workbench
      top={
        <TopBar
          facts={facts}
          demo={DEMO_MODE}
          repoUrl={REPO_URL}
          onHome={goHome}
          panelOpen={panelOpen}
          onTogglePanel={togglePanel}
          panelId={PANEL_ID}
          onSignOut={DEMO_MODE ? undefined : signOut}
          compact={compact}
          drawer={drawer}
        />
      }
      panel={
        <RequirementPanel
          id={PANEL_ID}
          open={panelOpen}
          onClose={closePanel}
          drawer={drawer}
          headMeta={facts?.version !== undefined ? `editing v${facts.version}` : undefined}
          notice={DEMO_MODE ? <DemoNotice repoUrl={REPO_URL} designOpen={!!result} /> : undefined}
        >
          {chat}
        </RequirementPanel>
      }
      tabs={
        <SheetTabs
          sheets={visibleTabs}
          active={activeTab}
          onSelect={setActiveTab}
          validationErrors={errorCount}
        />
      }
      status={<StatusBar facts={facts} demo={DEMO_MODE} />}
    >
      <SheetHost key={activeTab} sheet={sheet}>
        {!result ? (
          <EmptySheet sheets={visibleTabs} active={activeTab} demo={DEMO_MODE} />
        ) : (
          <>
            {activeTab === 'overview'   && (
              <OverviewSheet result={result} token={token} onOpenSheet={setActiveTab} />
            )}
            {activeTab === 'schematic'  && <SchematicViewer schematic={result.schematic} />}
            {activeTab === 'pcb'        && <PCBViewer netlist={result.pcb_netlist} token={token} />}
            {activeTab === 'firmware'   && (
              <FirmwareViewer
                circuitId={result.circuit_id}
                token={token}
                firmware={result.firmware}
                build={result.firmware_build}
                onBuild={handleFirmwareBuild}
              />
            )}
            {activeTab === 'simulation' && (
              <SimulationResults
                circuitId={(result as GenerateResponse).circuit_id}
                jobId={(result as GenerateResponse).simulation_job_id || null}
                token={token}
              />
            )}
            {activeTab === 'bom'        && (
              <BOMTable
                rows={(result as GenerateResponse).bom || []}
                circuitId={result.circuit_id}
                version={(result as PatchResponse).version}
                token={token}
                onPatched={handleBomPatched}
              />
            )}
            {activeTab === 'validation' && (
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
            )}
          </>
        )}
      </SheetHost>
    </Workbench>
  )
}
