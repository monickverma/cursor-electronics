'use client'

/**
 * Small primitives.
 *
 *   <EmptyState title="No firmware for this design" action={<Button>…</Button>}>
 *     It has no microcontroller.
 *   </EmptyState>
 *   <Kbd>Alt</Kbd> <Kbd>3</Kbd>
 *   <Cursor />                       // the blinking ▍ for work in progress (aria-hidden)
 *   <Cursor label="Compiling" />     // …with a screen-reader word
 *   <CopyButton value={circuitId} label="design id" />   // accessible name "Copy design id"
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, Copy } from 'lucide-react'
import { ICON } from './Button'

export function EmptyState({ title, children, action, className = '' }: {
  title: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={`empty ${className}`}>
      <p className="empty-title">{title}</p>
      {children && <div className="empty-body">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>
}

export function Cursor({ label }: { label?: string }) {
  return (
    <>
      <span className="cursor-blink" aria-hidden="true">▍</span>
      {label && <span className="sr-only">{label}</span>}
    </>
  )
}

export function CopyButton({ value, label = 'value', size = 'sm', className = '' }: {
  value: string
  /** What is copied, for the accessible name: "Copy <label>". */
  label?: string
  size?: 'sm' | 'md'
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 1400)
    } catch {
      // Clipboard refused (permissions, insecure context): nothing was copied, say nothing happened.
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className={`btn btn-ghost btn-square ${size === 'sm' ? 'btn-sm' : ''} ${className}`}
      aria-label={`Copy ${label}`}
      title={copied ? 'Copied' : `Copy ${label}`}
    >
      {copied ? <Check {...ICON} /> : <Copy {...ICON} />}
      <span className="sr-only" aria-live="polite">{copied ? 'Copied' : ''}</span>
    </button>
  )
}
