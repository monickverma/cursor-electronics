'use client'

/**
 * Workbench hooks. Everything that touches `window` or `localStorage` runs in an effect, so the
 * server render and the first client render agree (no hydration warnings).
 */
import { useCallback, useEffect, useState } from 'react'

/** Matches a media query after mount; `false` during SSR and the first client render. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const update = () => setMatches(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [query])
  return matches
}

/** Breakpoints of spec §5: ≥1100 full layout, 720–1100 drawer, <720 single column. */
export const BP_DRAWER = '(max-width: 1099.98px)'
export const BP_COMPACT = '(max-width: 719.98px)'

export const PANEL_MIN = 300
export const PANEL_MAX = 560
export const PANEL_DEFAULT = 380
const PANEL_KEY = 'circuitos.requirementPanel.width'

const clamp = (n: number) => Math.min(PANEL_MAX, Math.max(PANEL_MIN, Math.round(n)))

/**
 * Ctrl/⌘+B toggles the requirement panel; Alt+0…6 opens sheet 00…06. Uses `e.code` (Digit0…6)
 * because Alt+digit types a character on some keyboard layouts.
 */
export function useWorkbenchShortcuts(
  enabled: boolean,
  onTogglePanel: () => void,
  onSheetNumber: (n: number) => void,
) {
  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        onTogglePanel()
        return
      }
      if (e.altKey && !e.ctrlKey && !e.metaKey && /^Digit[0-6]$/.test(e.code)) {
        e.preventDefault()
        onSheetNumber(Number(e.code.slice(5)))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled, onTogglePanel, onSheetNumber])
}

/** The requirement panel's width, kept in localStorage (guarded: storage may be unavailable). */
export function usePanelWidth(): [number, (w: number) => void] {
  const [width, setWidthState] = useState(PANEL_DEFAULT)

  useEffect(() => {
    try {
      const saved = Number(window.localStorage.getItem(PANEL_KEY))
      if (Number.isFinite(saved) && saved > 0) setWidthState(clamp(saved))
    } catch {
      // Storage blocked (private mode, policy): keep the default.
    }
  }, [])

  const setWidth = useCallback((w: number) => {
    const next = clamp(w)
    setWidthState(next)
    try { window.localStorage.setItem(PANEL_KEY, String(next)) } catch { /* not persisted; still applied */ }
  }, [])

  return [width, setWidth]
}
