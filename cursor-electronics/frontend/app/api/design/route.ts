/**
 * Next.js proxy route → FastAPI backend.
 * Forwards POST /api/design to http://localhost:8000/design/generate
 * so the frontend never directly calls the backend from the browser (avoids CORS issues in prod).
 */

import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8000'

export async function POST(req: NextRequest) {
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
