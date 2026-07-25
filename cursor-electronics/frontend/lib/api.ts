const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function authHeaders(token?: string): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

export async function apiPost<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    let message: string
    if (Array.isArray(detail)) {
      // FastAPI validation error array
      message = detail.map((d: { msg?: string; loc?: string[] }) => `${d.loc?.slice(1).join('.')}: ${d.msg}`).join('; ')
    } else if (detail && typeof detail === 'object') {
      // Structured error object e.g. { error: 'circuit_generation_failed', attempts: [...] }
      if (detail.error === 'circuit_generation_failed' && Array.isArray(detail.attempts)) {
        message = `Circuit generation failed after ${detail.attempts.length} attempt(s). Last error: ${detail.attempts[detail.attempts.length - 1] ?? 'unknown'}`
      } else {
        message = JSON.stringify(detail)
      }
    } else {
      message = detail || `HTTP ${res.status}`
    }
    throw new Error(message)
  }
  return res.json()
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders(token) })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    let message: string
    if (Array.isArray(detail)) {
      message = detail.map((d: { msg?: string; loc?: string[] }) => `${d.loc?.slice(1).join('.')}: ${d.msg}`).join('; ')
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail)
    } else {
      message = detail || `HTTP ${res.status}`
    }
    throw new Error(message)
  }
  return res.json()
}

export interface GenerateResponse {
  circuit_id: string
  intent: string
  application_class: string
  target_mcu: string | null
  version: number
  simulation_job_id: string | null
  validation: { passed: boolean; errors: Array<{ field: string; message: string }>; warnings: Array<{ field: string; message: string }> }
  firmware: string | null
  schematic: string
  bom: BOMRow[]
  explanation: string
  ir: Record<string, unknown>
}

export interface BOMRow {
  id: string
  part_number: string
  manufacturer: string
  package: string
  value: string | null
  quantity: number
  lcsc_pn: string | null
  digikey_pn?: string | null
  unit_price_usd: number
  total_price_usd: number
  // Pricing provenance from BOMCompiler. `price_known: false` means the part is
  // absent from component_db.json — distinct from a genuinely $0.00 part.
  price_known?: boolean
  price_source?: 'part_number' | 'lcsc_pn' | 'part_number_prefix' | 'equivalent_value' | 'unknown'
  // Set when priced via a substitute: the database part the price came from.
  priced_as?: string | null
}

export interface SimulationStatus {
  job_id: string
  circuit_id: string
  status: string
  duration_ms?: number
  results?: Record<string, unknown>
  grade?: { passed: boolean; failures: string[]; notes: string[] }
  error?: string
}

export interface PatchResponse {
  circuit_id: string
  version: number
  changes: Array<{ component_id: string; field: string; new_value: unknown }>
  note_to_user: string
  validation: { passed: boolean; errors: Array<{ field: string; message: string }>; warnings: Array<{ field: string; message: string }> }
  simulation_job_id: string | null
  firmware: string | null
  schematic: string
  ir: Record<string, unknown>
}

export async function generateDesign(prompt: string, token: string): Promise<GenerateResponse> {
  return apiPost('/design/generate', { prompt }, token)
}

export async function pollSimulation(circuitId: string, jobId: string, token: string): Promise<SimulationStatus> {
  return apiGet(`/design/${circuitId}/simulation/${jobId}`, token)
}

export async function patchDesign(circuitId: string, command: string, token: string): Promise<PatchResponse> {
  return apiPost(`/design/${circuitId}/patch`, { command }, token)
}

export async function login(email: string, password: string): Promise<{ access_token: string }> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password }),
  })
  if (!res.ok) throw new Error('Invalid credentials')
  return res.json()
}

export async function register(email: string, password: string): Promise<{ access_token: string }> {
  return apiPost('/auth/register', { email, password })
}
