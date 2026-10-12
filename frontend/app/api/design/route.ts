/**
 * Next.js proxy route → FastAPI backend.
 * Forwards POST /api/design to ${BACKEND_URL}/design/generate (localhost:8000 in dev)
 * so the frontend never directly calls the backend from the browser (avoids CORS issues in prod).
 */

import { NextRequest, NextResponse } from 'next/server'

// localhost only in development: deployed, it would be the server's own
// loopback, where no backend runs. Unset in production, the route says so.
const BACKEND = process.env.BACKEND_URL ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '')

export async function POST(req: NextRequest) {
  if (!BACKEND) {
    return NextResponse.json(
      { detail: 'No backend is configured for this deployment (BACKEND_URL is unset). It runs in demo mode.' },
      { status: 503 },
    )
  }
  const token = req.headers.get('authorization') || ''
  const body = await req.text()

  const upstream = await fetch(`${BACKEND}/design/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: token } : {}),
    },
    body,
  })

  const data = await upstream.json()
  return NextResponse.json(data, { status: upstream.status })
}
