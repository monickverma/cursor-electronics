'use client'

/**
 * Top bar — 40px. The wordmark (a button back to the landing page), the loaded design's identity,
 * then the demo statement, Docs / GitHub, the requirement-panel toggle and Sign out.
 * Every design value comes from the response (`facts`); a value the response lacks is not drawn.
 */
import { ArrowUpRight, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { Chip, ICON } from '@/components/ui'
import type { DesignFacts } from './facts'

interface Props {
  facts: DesignFacts | null
  demo: boolean
  repoUrl: string
  onHome: () => void
  /** Omit to hide the panel toggle (e.g. on the sign-in screen). */
  panelOpen?: boolean
  onTogglePanel?: () => void
  panelId?: string
  /** Omit to hide Sign out (demo mode has no account). */
  onSignOut?: () => void
  compact?: boolean
  drawer?: boolean
}

export function TopBar({ facts, demo, repoUrl, onHome, panelOpen, onTogglePanel, panelId, onSignOut, compact, drawer }: Props) {
  return (
    <header className="tb">
      <button type="button" className="tb-brand" onClick={onHome} title="Back to the Circuit OS home page">
        <span className="tb-mark" aria-hidden="true" />
        <span className="t-wordmark">Circuit OS</span>
        <span className="sr-only">— back to the home page</span>
      </button>

      {facts ? (
        <div className="tb-design" aria-label="Loaded design">
          {!compact && facts.intent && (
            <span className="tb-intent" title={facts.intent}>{facts.intent}</span>
          )}
          {facts.version !== undefined && <Chip mono title="Revision">REV v{facts.version}</Chip>}
          {!drawer && facts.generator && <Chip mono title="Generator that derived this design">{facts.generator}</Chip>}
          {!compact && facts.targetMcu && <Chip mono title="Target board">{facts.targetMcu}</Chip>}
        </div>
      ) : (
        <div className="tb-spacer" />
      )}

      <div className="tb-right">
        {demo && (
          <div className="tb-cell">
            <Chip tone="warn" label title="Demo mode — recorded results. No backend is attached to this deployment.">
              {compact ? 'Demo' : 'Demo — recorded results'}
            </Chip>
          </div>
        )}
        {!compact && (
          <div className="tb-cell" style={{ gap: 0, padding: '0 4px' }}>
            <a className="btn btn-ghost btn-sm" href={`${repoUrl}#readme`} target="_blank" rel="noopener noreferrer">
              Docs<ArrowUpRight {...ICON} />
            </a>
            <a className="btn btn-ghost btn-sm" href={repoUrl} target="_blank" rel="noopener noreferrer">
              GitHub<ArrowUpRight {...ICON} />
            </a>
          </div>
        )}
        {onTogglePanel && (
          <div className="tb-cell" style={{ padding: '0 6px' }}>
            <button
              type="button"
              className="btn btn-ghost btn-square"
              onClick={onTogglePanel}
              aria-expanded={!!panelOpen}
              aria-controls={panelId}
              aria-label={panelOpen ? 'Hide requirement panel' : 'Show requirement panel'}
              title={`${panelOpen ? 'Hide' : 'Show'} requirement panel (Ctrl+B)`}
            >
              {panelOpen ? <PanelLeftClose {...ICON} /> : <PanelLeftOpen {...ICON} />}
            </button>
          </div>
        )}
        {onSignOut && (
          <div className="tb-cell" style={{ padding: '0 6px' }}>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onSignOut}>Sign out</button>
          </div>
        )}
      </div>
    </header>
  )
}
