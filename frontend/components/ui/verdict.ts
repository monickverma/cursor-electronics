/**
 * Verdict vocabulary — the one place that maps API states to colour, glyph and word (spec §3).
 * Colour is never the only signal: every tone travels with a glyph and a word.
 *
 *   verdictMeta('holds_defeasible')   // { tone: 'warn', glyph: '~', word: 'holds, defeasible' }
 *   propertyTone('refuted')           // 'fail'
 *   firmwareTone('compiling')         // 'neutral'
 */
import type { FirmwareStatus, PropertyView, Verdict } from '@/lib/api'

export type Tone = 'pass' | 'warn' | 'fail' | 'none'
/** `neutral` is chrome (no verdict) — e.g. work in progress. */
export type ToneOrNeutral = Tone | 'neutral'

export interface VerdictMeta {
  tone: Tone
  glyph: string
  word: string
  /** Not assessed and out of scope are drawn with a dashed border. */
  dashed: boolean
}

export const VERDICTS: Record<Verdict, VerdictMeta> = {
  holds:            { tone: 'pass', glyph: '✓', word: 'holds',             dashed: false },
  holds_defeasible: { tone: 'warn', glyph: '~', word: 'holds, defeasible', dashed: false },
  fails:            { tone: 'fail', glyph: '✕', word: 'fails',             dashed: false },
  not_assessed:     { tone: 'none', glyph: '–', word: 'not assessed',      dashed: true },
  out_of_scope:     { tone: 'none', glyph: '∅', word: 'out of scope',      dashed: true },
  not_applicable:   { tone: 'none', glyph: '·', word: 'not applicable',    dashed: false },
}

export const TONE_GLYPH: Record<Tone, string> = { pass: '✓', warn: '~', fail: '✕', none: '–' }

export function verdictMeta(v: Verdict): VerdictMeta {
  return VERDICTS[v] ?? { tone: 'none', glyph: '–', word: String(v).replace(/_/g, ' '), dashed: true }
}

export function propertyTone(status: PropertyView['status']): Tone {
  return status === 'proven' ? 'pass' : status === 'refuted' ? 'fail' : 'warn'
}

export function firmwareTone(status: FirmwareStatus | string): ToneOrNeutral {
  if (status === 'compiled') return 'pass'
  if (status === 'failed') return 'fail'
  if (status === 'compiling') return 'neutral'
  return 'none'
}
