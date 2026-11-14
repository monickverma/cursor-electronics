/**
 * Field, Input, Textarea — form controls on --bench-0 with a --line-2 border, white on focus.
 *
 *   <Field label="Email" hint="Any address; this is a local account.">
 *     <Input type="email" placeholder="Email address" value={email} onChange={…} required />
 *   </Field>
 *   <Textarea ref={ref} rows={1} placeholder="Describe your circuit…" />
 *
 * Field wraps its control in a <label>, so the control is named by the label text. If a test finds
 * the control by placeholder, keep the placeholder exactly as it is.
 * The bare classes `.input` / `.textarea` / `.select` work on native elements too.
 */
import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'

export function Field({ label, hint, error, children, className = '' }: {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <label className={`field ${className}`}>
      <span className="t-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && <span className="field-error" role="alert">{error}</span>}
    </label>
  )
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className = '', ...rest }, ref,
) {
  return <input ref={ref} className={`input ${className}`} {...rest} />
})

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className = '', ...rest }, ref,
) {
  return <textarea ref={ref} className={`textarea ${className}`} {...rest} />
})
