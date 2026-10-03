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
  // Stage 5: present only once it has compiled for the design's board.
  firmware: string | null
  firmware_build?: FirmwareBuild | null
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
  // Composition M4: present only on a composed board.
  blocks?: BlockView[]
  behaviour?: string[]
}

export interface BlockView {
  id: string
  function: string
  generator: string
  pin: string
  parts: string[]
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
  // Stage 6: a row is priced only as the exact part it names. Responses from
  // before Stage 6 may still say 'part_number_prefix' or 'equivalent_value'.
  // 'mouser': a live quote for that exact part number ([2026-09-25]).
  price_source?: 'part_number' | 'lcsc_pn' | 'unknown' | 'part_number_prefix' | 'equivalent_value' | 'mouser'
  // Stage 6: when the price was recorded, and what kind of price it is. For a
  // live quote, the time it was fetched (ISO, UTC).
  price_asof?: string | null
  price_note?: string | null
  // The price shown and its currency: the static catalogue's USD, or a live
  // quote's own currency — never converted. `unit_price_usd` stays static.
  unit_price?: number | null
  currency?: string | null
  live?: LivePrice | null
  // Always null since Stage 6; kept so older stored responses still type.
  priced_as?: string | null
}

// [2026-09-25]: a live distributor quote for the exact part number.
export interface LivePrice {
  source: 'mouser'
  distributor_pn: string | null
  currency: string
  unit_price: number
  price_break: number
  breaks: { quantity: number; unit_price: number }[]
  stock: number | null
  min_order: number | null
  order_multiple: number | null
  product_url: string | null
  fetched_at: string
}

export interface CurrencyTotal {
  currency: string
  amount: number
  rows: number
  sources: string[]
}

// ── Stage 6: substitutes, each checked against the original's checks ───────

export interface PatchOpJSON {
  op: 'add' | 'remove' | 'replace' | 'test'
  path: string
  value?: unknown
}

export interface Substitute {
  component_id: string
  part_number: string
  package: string
  replaces: string
  changes: string[]              // "R1: RC0402FR-0710KL → RC0603FR-0710KL", "package 0402 → 0603", …
  unit_price_usd?: number | null
  price_asof?: string | null
  price_delta_usd?: number | null
  live?: LivePrice | null        // a cached or fetched Mouser quote, shown beside; never decides
  checks: number                 // claims and properties re-checked
  ops: PatchOpJSON[]             // the patch that applies it
}

export interface RejectedSubstitute {
  component_id: string
  part_number: string
  reason: string
}

export interface BOMView {
  circuit_id: string
  version: number
  rows: BOMRow[]
  total_usd: number              // the static catalogue total
  totals?: CurrencyTotal[]       // what the rows show, one total per currency
  coverage: { priced: number; total: number; complete: boolean; unpriced_ids: string[] }
  pricing: string
  live_pricing?: {
    enabled: boolean
    source: string
    requested: number
    quoted: number
    from_cache: number
    fetched: number
    error: string | null           // Mouser could not price the rows; they stay static
    cache_error?: string | null    // the price cache failed; the prices shown are unaffected
  }
  substitutes: Substitute[]
  rejected: RejectedSubstitute[]
  substitutes_unavailable: string | null
}

export async function getBom(circuitId: string, token: string): Promise<BOMView> {
  return apiGet(`/design/${circuitId}/bom`, token)
}

// Applying a substitute is an ordinary patch to the requirement: zero model
// calls, a new version, the design re-derived through the same gate.
export async function applyPatchOps(circuitId: string, ops: PatchOpJSON[], token: string): Promise<PatchResponse> {
  return apiPost(`/design/${circuitId}/patch`, { ops }, token)
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
  firmware_build?: FirmwareBuild | null
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

// ── Stage 5: firmware is shown only once it compiles ────────────────────────

export type FirmwareStatus = 'none' | 'compiling' | 'compiled' | 'failed' | 'unavailable'

export interface FirmwareBuild {
  status: FirmwareStatus
  message: string
  target?: string | null   // data/mcu_targets id, e.g. esp32_devkitc
  board?: string | null    // e.g. "ESP32-DevKitC (ESP32-WROOM-32E)"
  build?: string | null    // SHA-256 of the PlatformIO project
  firmware?: string | null
  platformio_ini?: string | null
  log?: string | null      // the build log's tail, when it failed
}

export async function getFirmware(circuitId: string, token: string): Promise<FirmwareBuild> {
  return apiGet(`/design/${circuitId}/firmware`, token)
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
