/**
 * VerdictBadge — a verdict as glyph + word in its colour. Never colour alone.
 *
 *   <VerdictBadge verdict={claim.verdict} />                      // ✓ holds  /  – not assessed (dashed)
 *   <VerdictBadge tone={propertyTone(p.status)} label={p.status} />
 *   <VerdictBadge tone="fail" label="FAIL" glyph="✕" />
 *   <VerdictBadge verdict="holds" plain />                         // no box: glyph + word inline (dense tables)
 *   <VerdictBadge verdict="fails" glyphOnly />                     // glyph only; the word stays for screen readers
 *
 * Tones: pass | warn | fail | none (grey; dashed for not assessed / out of scope).
 * Helpers for mapping states live in ./verdict (verdictMeta, propertyTone, firmwareTone).
 */
import type { Verdict } from '@/lib/api'
import { TONE_GLYPH, verdictMeta, type Tone } from './verdict'

type Props = {
  plain?: boolean
  glyphOnly?: boolean
  className?: string
  title?: string
} & (
  | { verdict: Verdict; tone?: never; label?: string; glyph?: string; dashed?: boolean }
  | { verdict?: never; tone: Tone; label: string; glyph?: string; dashed?: boolean }
)

export function VerdictBadge(props: Props) {
  const { plain, glyphOnly, className = '', title } = props
  let tone: Tone
  let glyph: string
  let word: string
  let dashed: boolean
  if (props.verdict) {
    const m = verdictMeta(props.verdict)
    tone = m.tone
    glyph = props.glyph ?? m.glyph
    word = props.label ?? m.word
    dashed = props.dashed ?? m.dashed
  } else {
    tone = props.tone
    glyph = props.glyph ?? TONE_GLYPH[props.tone]
    word = props.label
    dashed = props.dashed ?? props.tone === 'none'
  }
  const cls = [
    'chip', 'verdict', `chip-${tone}`,
    plain ? 'verdict-plain' : '',
    !dashed && tone === 'none' ? 'chip-none-solid' : '',
    className,
  ].filter(Boolean).join(' ')
  return (
    <span className={cls} title={title}>
      <span className="verdict-glyph" aria-hidden="true">{glyph}</span>
      {glyphOnly ? <span className="sr-only">{word}</span> : <span>{word}</span>}
    </span>
  )
}

/** A grade `G0`–`G7` in mono. `null` prints a dashed "no grade" chip rather than inventing one. */
export function GradeChip({ grade, className = '', title }: { grade: string | null | undefined; className?: string; title?: string }) {
  if (!grade) {
    return <span className={`grade grade-empty ${className}`} title={title ?? 'no grade'}>–</span>
  }
  return <span className={`grade ${className}`} title={title}>{grade}</span>
}
