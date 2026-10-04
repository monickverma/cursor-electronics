'use client'

/**
 * The design's explanation, which arrives after the design does ([2026-10-05]).
 * The generate response says `writing`; this polls GET /design/{id}/explanation
 * every 3 s until it is written or has failed, and says which. An explanation
 * that could not be written shows its reason; it is never just absent.
 */

import { useEffect, useState } from 'react'
import { getExplanation, type ExplanationView } from '@/lib/api'

interface Props {
  circuitId?: string
  token?: string
  explanation?: string
  status?: string
  error?: string | null
}

const SETTLED = new Set(['written', 'failed', 'unavailable'])

export default function ExplanationPanel({ circuitId, token, explanation, status, error }: Props) {
  const [view, setView] = useState<ExplanationView>({
    status: explanation ? 'written' : (status ?? 'written'), explanation: explanation ?? '', error: error ?? null,
  })

  useEffect(() => {
    setView({ status: explanation ? 'written' : (status ?? 'written'), explanation: explanation ?? '', error: error ?? null })
  }, [circuitId, explanation, status, error])

  const current = view.status
  useEffect(() => {
    if (!circuitId || !token || current !== 'writing') return
    let stopped = false
    const poll = async () => {
      try {
        const next = await getExplanation(circuitId, token)
        if (!stopped) setView(next)
      } catch {
        // A failed poll is retried on the next tick.
      }
    }
    poll()
    const timer = setInterval(poll, 3000)
    return () => {
      stopped = true
      clearInterval(timer)   // cleanup on unmount, and once the status settles
    }
  }, [circuitId, token, current])

  if (view.status === 'writing') {
    return (
      <p className="text-sm text-muted border border-border rounded p-3">
        Writing the explanation. The design above is complete; this usually takes about a minute.
      </p>
    )
  }
  if (!view.explanation) {
    if (!SETTLED.has(view.status) || !view.error) return null
    return (
      <p className="text-sm text-muted border border-border rounded p-3">
        No explanation for this design: {view.error}.
      </p>
    )
  }
  return (
    <section>
      <h3 className="text-sm font-medium text-cream mb-3" style={{ fontFamily: 'EB Garamond, serif' }}>
        Design Explanation
      </h3>
      <div className="text-sm text-cream-dim leading-relaxed whitespace-pre-wrap bg-surface border border-border rounded p-4">
        {view.explanation}
      </div>
    </section>
  )
}
