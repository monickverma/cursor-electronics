'use client'

/**
 * A window on the flow desktop.
 *
 * It sits in the page's normal layout and is moved with a transform, so the
 * desktop still reflows at any width. It bobs slightly, can be dragged by its
 * title bar, keeps the speed it is thrown with, and stirs the water as it goes
 * (lib/flow.ts). The bob freezes exactly where it is while the pointer or the
 * keyboard focus is inside it, and carries on from there afterwards: nothing a
 * person is reading or aiming at moves, not even to settle.
 *
 * `tone` picks the palette of whatever is inside — see tailwind.config.ts.
 */

import { useEffect, useRef, ReactNode, PointerEvent as ReactPointerEvent } from 'react'
import { nextZ, prefersCalm, pushSplat } from '@/lib/flow'

interface Props {
  id: string
  title: string
  meta?: ReactNode
  tone?: 'paper' | 'screen'
  /** Body height in px. Omit to let the content decide. */
  height?: number
  /** Changing this number raises the window and scrolls it into view. */
  focusKey?: number
  onHide?: () => void
  className?: string
  children: ReactNode
}

interface Motion {
  x: number; y: number; vx: number; vy: number
  phase: number
  /** The bob's own clock. It only runs while nobody is inside the window. */
  bobT: number
  held: boolean; inside: boolean
  px: number; py: number; pt: number
  drawn: string
}

const DRAG_LIMIT_X = 900
const DRAG_LIMIT_Y = 700
const MAX_THROW = 900          // px/s

export default function FloatWindow({ id, title, meta, tone = 'paper', height, focusKey, onHide, className, children }: Props) {
  const elRef = useRef<HTMLElement>(null)
  const motion = useRef<Motion>({
    x: 0, y: 0, vx: 0, vy: 0,
    phase: id.split('').reduce((n, c) => n + c.charCodeAt(0), 0) * 0.37,
    bobT: 0, held: false, inside: false, px: 0, py: 0, pt: 0, drawn: '',
  })

  useEffect(() => {
    const el = elRef.current
    if (!el) return
    const m = motion.current
    const calm = prefersCalm()
    let raf = 0
    let last = performance.now()

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      const dt = Math.min(0.033, Math.max(0.001, (now - last) / 1000))
      last = now

      const damp = Math.exp(-(m.held ? 8 : 2.2) * dt)
      m.vx *= damp
      m.vy *= damp
      if (!m.held) {
        m.x = Math.max(-DRAG_LIMIT_X, Math.min(DRAG_LIMIT_X, m.x + m.vx * dt))
        m.y = Math.max(-DRAG_LIMIT_Y, Math.min(DRAG_LIMIT_Y, m.y + m.vy * dt))
      }

      if (!m.held && !m.inside) m.bobT += dt
      const amp = calm ? 0 : 1
      const bx = Math.cos(m.bobT * 0.45 + m.phase * 1.7) * 3 * amp
      const by = Math.sin(m.bobT * 0.7 + m.phase) * 5 * amp
      const tilt = Math.max(-2.5, Math.min(2.5, m.vx * 0.004))

      const next = `translate3d(${(m.x + bx).toFixed(1)}px,${(m.y + by).toFixed(1)}px,0) rotate(${tilt.toFixed(2)}deg)`
      if (next !== m.drawn) {
        el.style.transform = next
        m.drawn = next
      }

      const speed = Math.hypot(m.vx, m.vy)
      if (speed > 40) {
        const r = el.getBoundingClientRect()
        const w = window.innerWidth || 1
        const h = window.innerHeight || 1
        pushSplat({
          x: (r.left + r.width / 2) / w,
          y: 1 - (r.top + r.height / 2) / h,
          dx: (m.vx / w) * dt * 14,
          dy: (-m.vy / h) * dt * 14,
          dye: Math.min(0.5, speed * 0.0006),
          r: 0.012,
        })
      }
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [])

  // A dock button asked for this window: bring it forward and into view.
  useEffect(() => {
    const el = elRef.current
    if (!el || focusKey === undefined) return
    el.style.zIndex = String(nextZ())
    if (focusKey > 0) el.scrollIntoView({ block: 'nearest', behavior: prefersCalm() ? 'auto' : 'smooth' })
  }, [focusKey])

  function raise() {
    if (elRef.current) elRef.current.style.zIndex = String(nextZ())
  }

  function onBarDown(e: ReactPointerEvent<HTMLDivElement>) {
    // The hide button lives in the bar; pressing it is not a drag.
    if ((e.target as HTMLElement).closest('button')) return
    const m = motion.current
    m.held = true
    m.vx = 0
    m.vy = 0
    m.px = e.clientX
    m.py = e.clientY
    m.pt = performance.now()
    e.currentTarget.setPointerCapture(e.pointerId)
    raise()
    e.preventDefault()
  }

  function onBarMove(e: ReactPointerEvent<HTMLDivElement>) {
    const m = motion.current
    if (!m.held) return
    const now = performance.now()
    const dx = e.clientX - m.px
    const dy = e.clientY - m.py
    const dt = Math.max(8, now - m.pt) / 1000
    m.x += dx
    m.y += dy
    m.vx = Math.max(-MAX_THROW, Math.min(MAX_THROW, 0.6 * m.vx + 0.4 * (dx / dt)))
    m.vy = Math.max(-MAX_THROW, Math.min(MAX_THROW, 0.6 * m.vy + 0.4 * (dy / dt)))
    m.px = e.clientX
    m.py = e.clientY
    m.pt = now
  }

  function onBarUp(e: ReactPointerEvent<HTMLDivElement>) {
    motion.current.held = false
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
  }

  return (
    <section
      ref={elRef}
      aria-label={title}
      data-testid={`window-${id}`}
      className={`win ${className ?? ''}`}
      onPointerEnter={() => { motion.current.inside = true }}
      onPointerLeave={() => { motion.current.inside = false }}
      onFocusCapture={() => { motion.current.inside = true }}
      onBlurCapture={() => { motion.current.inside = false }}
      onPointerDownCapture={raise}
    >
      <div className="win-in">
        <div
          className="win-bar"
          onPointerDown={onBarDown}
          onPointerMove={onBarMove}
          onPointerUp={onBarUp}
          onPointerCancel={onBarUp}
        >
          <span className="truncate">{title}</span>
          <span className="flex items-center gap-2 min-w-0">
            {meta && <span className="truncate">{meta}</span>}
            {onHide && (
              <button type="button" className="win-hide" onClick={onHide} aria-label={`Hide ${title}`}>
                ×
              </button>
            )}
          </span>
        </div>
        <div className={`${tone} overflow-hidden`} style={height ? { height } : undefined}>
          {children}
        </div>
      </div>
    </section>
  )
}
