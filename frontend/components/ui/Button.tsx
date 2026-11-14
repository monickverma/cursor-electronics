/**
 * Button — the only button style in the app.
 *
 *   <Button variant="primary" onClick={send}>Send</Button>
 *   <Button variant="secondary" size="sm" icon={<Download {...ICON} />}>Download .ino</Button>
 *   <Button variant="ghost" square aria-label="Copy hash" icon={<Copy {...ICON} />} />
 *   <Button variant="secondary" aria-pressed={is3d}>3D</Button>   // pressed = inverted, never coloured
 *
 * variant: primary (white fill, the one main action per area) | secondary (hairline) | ghost (text) |
 *          danger (fail text + border; only for actions that discard something)
 * size:    sm 24px | md 28px (default) | lg 36px
 * square:  icon-only, width = height. Always give it an aria-label.
 * The accessible name is the text you pass — tests query buttons by exact name, so keep wording.
 * `type` defaults to "button" (never submits a form by accident); pass type="submit" in forms.
 */
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  square?: boolean
  /** An icon before the label (lucide at 14px, stroke 1.5 — spread `ICON`). */
  icon?: ReactNode
  /** An icon after the label. */
  iconRight?: ReactNode
}

/** Props for lucide-react icons: 14px, stroke 1.5. `<Download {...ICON} />` */
export const ICON = { size: 14, strokeWidth: 1.5, 'aria-hidden': true } as const

export function buttonClass(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md', square = false, extra = '') {
  return ['btn', `btn-${variant}`, size !== 'md' ? `btn-${size}` : '', square ? 'btn-square' : '', extra]
    .filter(Boolean)
    .join(' ')
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', square = false, icon, iconRight, className = '', type = 'button', children, ...rest },
  ref,
) {
  return (
    <button ref={ref} type={type} className={buttonClass(variant, size, square, className)} {...rest}>
      {icon}
      {children}
      {iconRight}
    </button>
  )
})
