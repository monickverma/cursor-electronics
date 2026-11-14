/**
 * Facts about the loaded design, read only from the API response. Anything the response does
 * not carry is `undefined`/`null` here, and the shell omits it — never a guessed value or a zero.
 *
 * A PatchResponse carries no top-level intent / application_class / target_mcu; those are read
 * from its `ir`, which is the stored design the response returns.
 */
import type { FirmwareBuild, GenerateResponse, PatchResponse, ValidationCoverage, Verdict } from '@/lib/api'

export type DesignResult = GenerateResponse | PatchResponse

export interface DesignFacts {
  circuitId: string
  version: number | undefined
  intent: string | undefined
  applicationClass: string | undefined
  targetMcu: string | undefined
  generator: string | undefined
  validation: DesignResult['validation'] | undefined
  coverage: ValidationCoverage | null
  firmwareBuild: FirmwareBuild | null
  bomCount: number | null
  simulationJobId: string | null
  componentCount: number | null
  netCount: number | null
}

const str = (v: unknown): string | undefined => (typeof v === 'string' && v.trim() ? v : undefined)

export function designFacts(result: DesignResult): DesignFacts {
  const ir = (result.ir ?? {}) as Record<string, unknown>
  const g = result as Partial<GenerateResponse>
  const p = result as Partial<PatchResponse>
  return {
    circuitId: result.circuit_id,
    version: typeof result.version === 'number' ? result.version : undefined,
    intent: str(g.intent) ?? str(ir.intent),
    applicationClass: str(g.application_class) ?? str(ir.application_class),
    targetMcu: str(g.target_mcu) ?? str(ir.target_mcu),
    generator: str(p.generator) ?? str(ir.generator),
    validation: result.validation ?? undefined,
    coverage: result.validation_coverage ?? null,
    firmwareBuild: result.firmware_build ?? null,
    bomCount: Array.isArray(g.bom) ? g.bom.length : null,
    simulationJobId: result.simulation_job_id || null,
    componentCount: Array.isArray(ir.components) ? ir.components.length : null,
    netCount: Array.isArray(ir.nodes) ? ir.nodes.length : null,
  }
}

export interface ClaimCounts {
  holds: number
  defeasible: number
  fails: number
  /** not assessed + out of scope */
  open: number
  notApplicable: number
  total: number
}

export function claimCounts(coverage: ValidationCoverage): ClaimCounts {
  const by = (v: Verdict) => coverage.claims.filter(c => c.verdict === v).length
  return {
    holds: by('holds'),
    defeasible: by('holds_defeasible'),
    fails: by('fails'),
    open: by('not_assessed') + by('out_of_scope'),
    notApplicable: by('not_applicable'),
    total: coverage.claims.length,
  }
}

export function claimCountsTitle(c: ClaimCounts): string {
  return `${c.total} claims: ${c.holds} hold, ${c.defeasible} hold defeasibly, ${c.fails} fail, ` +
    `${c.open} not assessed or out of scope, ${c.notApplicable} not applicable`
}
