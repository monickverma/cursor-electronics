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
        // Show every attempt, not just the last. The attempts usually differ,
        // and the first one is the most diagnostic — later retries carry the
        // earlier IR in their context, so their errors are downstream of it.
        const attempts = detail.attempts as string[]
        message = attempts.length
          ? `Circuit generation failed after ${attempts.length} attempt(s):\n` +
            attempts.map((a, i) => `  ${i + 1}. ${a}`).join('\n')
          : 'Circuit generation failed with no recorded attempts.'
      } else if (detail.error === 'out_of_envelope' && Array.isArray(detail.refusals)) {
        // A refusal is a product outcome with reasons, not a crash.
        const kept = detail.kept_version ? ` The design is unchanged (still v${detail.kept_version}).` : ''
        const reasons = (detail.refusals as Array<{ generator: string; reason: string }>)
          .map(r => `  - ${r.generator}: ${r.reason}`)
        message = ['No generator accepts that requirement:', ...reasons].join('\n') + kept
      } else if (typeof detail.message === 'string') {
        message = detail.message
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
  pcb_netlist?: Record<string, unknown>
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
  // Stage 2: the requirement diff, one line per changed path —
  // "targets.cutoff_hz: 1000 → 2000". Patches edit the requirement, not parts.
  changes: string[]
  note_to_user: string
  validation: { passed: boolean; errors: Array<{ field: string; message: string }>; warnings: Array<{ field: string; message: string }> }
  simulation_job_id: string | null
  firmware: string | null
  schematic: string
  pcb_netlist?: Record<string, unknown>
  ir: Record<string, unknown>
  intent_ir?: Record<string, unknown>
  predict_delta?: string[]
  citations?: string[]
  generator?: string | null
  generator_changed?: { from: string; to: string } | null
  annotations?: { attached: unknown[]; orphaned: unknown[] }
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

export interface PCBCompileResponse {
  svg: string
  stats: {
    name?: string
    size_mm?: [number, number]
    components?: number
    pads?: number
    nets?: number
    connections?: number
    routed?: number
    unrouted?: number
    drc_errors?: number
    vias?: number
    copper_mm?: number
  }
  warnings: string[]
  violations: string[]
}

export async function compilePCB(
  netlist: Record<string, unknown>,
  token: string,
): Promise<PCBCompileResponse> {
  return apiPost('/pcb/compile', netlist, token)
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

export interface HealthResponse {
  status: string
  environment: string
  pcb_engine_enabled: boolean
}

// Used to decide which tabs exist. Failure is treated as "off" by the caller:
// a tab wired to an unreachable backend is the same dead click as a tab wired
// to a disabled route.
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}
