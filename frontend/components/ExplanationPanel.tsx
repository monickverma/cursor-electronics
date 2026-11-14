'use client'

/**
 * The design's explanation, which arrives after the design does ([2026-10-05]).
 * The generate response says `writing`; this polls GET /design/{id}/explanation
 * every 3 s until it is written or has failed, and says which. An explanation
 * that could not be written shows its reason; it is never just absent.
 */

import { useEffect, useState } from 'react'
import { getExplanation, type ExplanationView } from '@/lib/api'
import { Callout, Cursor, Prose } from '@/components/ui'

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
      <p className="t-small c-fg-2" role="status">
        Writing the explanation. The design above is complete; this usually takes about a minute.{' '}
        <Cursor label="writing" />
      </p>
    )
  }
  if (!view.explanation) {
    if (!SETTLED.has(view.status) || !view.error) return null
    // Not a verdict on the design: an informational (grey) note.
    return (
      <Callout>
        No explanation for this design: {view.error}.
      </Callout>
    )
  }
  return <Prose text={view.explanation} />
}
