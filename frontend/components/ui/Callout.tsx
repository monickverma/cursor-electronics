/**
 * Callout — a statement set apart by a 2px left rule. Fill only in the tone's -bg.
 *
 *   <Callout tone="fail" title="Generation refused">{message}</Callout>
 *   <Callout tone="warn" title="Experimental">The PCB engine is not part of the v0.1.0 gate.</Callout>
 *   <Callout>Plain information, grey rule, no fill.</Callout>
 *
 * tone: info (default) | pass | warn | fail.  Use warn/fail/pass only when the text is a verdict
 *   or a statement about evidence (a refusal, a failure, a doubt) — colour means a verdict.
 * role: pass role="alert" for an error that appears in response to the user's action.
 */
import type { HTMLAttributes, ReactNode } from 'react'

export type CalloutTone = 'info' | 'pass' | 'warn' | 'fail'

interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  tone?: CalloutTone
  title?: ReactNode
  children?: ReactNode
}

export function Callout({ tone = 'info', title, children, className = '', ...rest }: Props) {
  return (
    <div className={`callout callout-${tone} ${className}`} {...rest}>
      {title && <div className="callout-title">{title}</div>}
      {children && <div className={title ? 'mt-1' : undefined}>{children}</div>}
    </div>
  )
}
