/**
 * Chip — a small hairline tag. Neutral by default; a tone only when it states a verdict.
 *
 *   <Chip mono>D1</Chip>                       // ids, defeaters, part numbers
 *   <Chip label>static</Chip>                  // uppercase lettering (e.g. a price source)
 *   <Chip tone="warn" label>Demo — recorded results</Chip>
 *   <Chip solid mono>REV v3</Chip>             // inverted (selected / emphasis), still not a colour
 *
 * tone: neutral | pass | warn | fail | none.  Do not colour a chip for decoration.
 */
import type { HTMLAttributes, ReactNode } from 'react'
import type { ToneOrNeutral } from './verdict'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: ToneOrNeutral
  mono?: boolean
  label?: boolean
  solid?: boolean
  children: ReactNode
}

export function Chip({ tone = 'neutral', mono, label, solid, className = '', children, ...rest }: Props) {
  const cls = [
    'chip',
    tone !== 'neutral' ? `chip-${tone}` : '',
    mono ? 'chip-mono' : '',
    label ? 'chip-label' : '',
    solid ? 'chip-solid' : '',
    className,
  ].filter(Boolean).join(' ')
  return <span className={cls} {...rest}>{children}</span>
}
