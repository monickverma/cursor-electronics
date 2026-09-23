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
  validation_coverage?: ValidationCoverage | null
}

// ── Stage 3: claim objects (EVIDENCE_CLASSES.md §3) ─────────────────────────

export type Verdict =
  | 'holds' | 'holds_defeasible' | 'fails'
  | 'not_applicable' | 'not_assessed' | 'out_of_scope'

export interface Claim {
  id: string
  claim: string
  kind: 'analytic' | 'empirical' | 'projected'
  verdict: Verdict
  method: string | null
  grade: string | null
  scope: { parameters: string; horizon: string; model: string; inputs: string } | null
  defeaters: string[]
  critical: boolean
  detail: string | null
  covers: string[]
}

// ── Stage 4: proved properties (backend/proof, validation/claims.py) ────────

export interface PropertyView {
  id: string
  /** The sentence proved, generated from the formula by template — what is signed. */
  english: string
  hash: string
  status: 'proven' | 'refuted' | 'unknown'
  method: string
  grade: string | null
  re_derives: string | null
  counterexample: Record<string, string> | null
}

export interface ValidationCoverage {
  claims: Claim[]
  coverage_le_g2: number
  grade_floor: string | null
  open_defeaters: string[]
  not_assessed: string[]
  out_of_scope: string[]
  // Stage 4. Absent on designs built before it.
  properties?: PropertyView[]
  properties_hash?: string | null
  properties_signed?: boolean
  signed_by?: string | null
}

export interface SignOffResponse {
  circuit_id: string
  version: number
  signed_by: string
  properties_hash: string
  validation_coverage: ValidationCoverage
  intent_ir: Record<string, unknown>
}

/** Sign the properties the user was shown. The hash is the one displayed, never recomputed. */
export async function signOffDesign(
  circuitId: string, propertiesHash: string, token: string,
): Promise<SignOffResponse> {
  return apiPost(`/design/${circuitId}/sign-off`, { properties_hash: propertiesHash }, token)
}

// ── Stage 3: waveform data (backend/simulation/waveforms.py) ────────────────

export interface Sweep {
  x: number[]
  series: Record<string, Array<number | null>>
}

export interface Waveforms {
  dc: { voltages: Record<string, number>; currents: Record<string, number> }
  ac: Sweep
  tran: Sweep
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
  results?: {
    dc_voltages?: Record<string, number>
    ac_points_count?: number
    // Absent on results stored before Stage 3.
    waveforms?: Waveforms | null
  }
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
  validation_coverage?: ValidationCoverage | null
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
