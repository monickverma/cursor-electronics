'use client'

/**
 * The workbench grid: top bar (40) / body / status bar (26). The body is the requirement panel
 * beside the main column (sheet tabs over the sheet). Pass the parts as slots:
 *
 *   <Workbench top={<TopBar …/>} panel={<RequirementPanel …/>} tabs={<SheetTabs …/>} status={<StatusBar …/>}>
 *     <SheetHost sheet={…}>{panel content}</SheetHost>
 *   </Workbench>
 *
 * Landmarks: header (top bar), aside (requirement panel), main (sheets), footer (status bar).
 */
import type { ReactNode } from 'react'

export function Workbench({ top, panel, tabs, status, children }: {
  top: ReactNode
  panel?: ReactNode
  tabs?: ReactNode
  status: ReactNode
  children: ReactNode
}) {
  return (
    <div className="wb">
      {top}
      <div className="wb-body">
        {panel}
        <main className="wb-main" id="sheets">
          {tabs}
          {children}
        </main>
      </div>
      {status}
    </div>
  )
}

/**
 * Live mode before sign-in: the sign-in panel centred in the sheet area, in the same frame.
 * ChatPanel renders the form itself (placeholders `Email address` / `Password`, buttons
 * `Sign in` / `Create account`), so it is hosted here unchanged.
 */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div className="auth h-full">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-head">
          <h1 id="auth-title" className="t-label">Account</h1>
          <span className="t-data c-fg-3">live backend</span>
        </div>
        <div className="auth-body">{children}</div>
        <p className="auth-foot">Designs are stored per account on the backend you are connected to.</p>
      </section>
    </div>
  )
}
