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
 *
 * Two buttons in the title bar take a window out of the layout: one docks it to
 * the right half of the screen, the other makes it full screen (the browser's
 * Fullscreen API, so it covers the library too and Esc leaves it). Double-click
 * the title bar for full screen. While docked or full screen it neither bobs nor
 * drags. A half dock on a wide screen is a split screen: the rest of the desktop
 * moves into the left half (globals.css). Full screen holds the window's place
 * with an empty box of its old height, so the page does not jump on the way back.
 * One window is out of the layout at a time.
 */

import { useEffect, useLayoutEffect, useRef, useState, ReactNode, PointerEvent as ReactPointerEvent } from 'react'
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
  /** Show the right-half and full-screen buttons. */
  maximizable?: boolean
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

/** Where the window is: in the layout, docked to the right half, or full screen. */
type Size = 'normal' | 'half' | 'full'

/** Sent (with the window's id) when a window leaves the layout; any other one out goes back. */
const OUT_EVENT = 'flow:window-out'

function IconHalf() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="11" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <rect x="8" y="2.5" width="6.5" height="11" fill="currentColor" />
    </svg>
  )
}

function IconFull({ on }: { on: boolean }) {
  // Corners pointing out to enter, pointing in to leave.
  const d = on
    ? 'M6 1.5V6H1.5M10 1.5V6h4.5M6 14.5V10H1.5M10 14.5V10h4.5'
    : 'M1.5 6V1.5H6M14.5 6V1.5H10M1.5 10v4.5H6M14.5 10v4.5H10'
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

export default function FloatWindow({ id, title, meta, tone = 'paper', height, focusKey, onHide, maximizable = false, className, children }: Props) {
  const elRef = useRef<HTMLElement>(null)
  const [size, setSize] = useState<Size>('normal')
  const sizeRef = useRef<Size>('normal')
  sizeRef.current = size
  // The window's height in the layout, kept while it is out of it.
  const [holdHeight, setHoldHeight] = useState(0)
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

      // Docked or full screen: stand still, exactly where it was put.
      if (sizeRef.current !== 'normal') {
        if (m.drawn !== 'none') {
          el.style.transform = 'none'
          m.drawn = 'none'
        }
        m.vx = 0
        m.vy = 0
        return
      }

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

  // Leaving full screen by Esc (or any way but our button) puts the window back.
  useEffect(() => {
    const onChange = () => {
      if (document.fullscreenElement !== elRef.current && sizeRef.current === 'full') setSize('normal')
    }
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  // Out of the layout, the window stands exactly in its slot from the first frame:
  // the bob's offset is cleared now, not on the next animation frame (which the
  // browser may hold back), or a docked window sits a few pixels off the edge.
  useLayoutEffect(() => {
    const el = elRef.current
    if (!el || size === 'normal') return
    el.style.transform = 'none'
    motion.current.drawn = 'none'
  }, [size])

  // One window out of the layout at a time: docking another puts this one back,
  // rather than stacking two windows invisibly in the same place.
  useEffect(() => {
    const onOut = (e: Event) => {
      if ((e as CustomEvent<string>).detail === id || sizeRef.current === 'normal') return
      if (document.fullscreenElement === elRef.current) document.exitFullscreen().catch(() => {})
      setSize('normal')
    }
    window.addEventListener(OUT_EVENT, onOut)
    return () => window.removeEventListener(OUT_EVENT, onOut)
  }, [id])

  // Esc also undocks a half-screen window, unless it was pressed in a text field.
  useEffect(() => {
    if (size !== 'half') return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return
      setSize('normal')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [size])

  function raise() {
    if (elRef.current) elRef.current.style.zIndex = String(nextZ())
  }

  function leaveLayout() {
    // Measure before the window leaves the layout, so its place can be held.
    if (sizeRef.current === 'normal' && elRef.current) setHoldHeight(elRef.current.offsetHeight)
    window.dispatchEvent(new CustomEvent(OUT_EVENT, { detail: id }))
  }

  function toggleHalf() {
    if (sizeRef.current === 'half') { setSize('normal'); return }
    if (document.fullscreenElement === elRef.current) document.exitFullscreen().catch(() => {})
    leaveLayout()
    raise()
    setSize('half')
  }

  async function toggleFull() {
    const el = elRef.current
    if (!el) return
    if (sizeRef.current === 'full') {
      setSize('normal')
      if (document.fullscreenElement === el) await document.exitFullscreen().catch(() => {})
      return
    }
    leaveLayout()
    raise()
    setSize('full')
    try {
      await el.requestFullscreen()
    } catch {
      // No Fullscreen API here (or it was refused): fill the window instead.
    }
  }

  function onBarDown(e: ReactPointerEvent<HTMLDivElement>) {
    // The bar's buttons are not a drag, and a docked window does not move.
    if ((e.target as HTMLElement).closest('button')) return
    if (sizeRef.current !== 'normal') return
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

  const out = size !== 'normal'

  return (
    <>
      {out && <div aria-hidden="true" className="win-hold" data-for={size} style={{ height: holdHeight }} />}
      <section
        ref={elRef}
        aria-label={title}
        data-testid={`window-${id}`}
        data-size={size}
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
            onDoubleClick={e => { if (maximizable && !(e.target as HTMLElement).closest('button')) toggleFull() }}
          >
            <span className="truncate">{title}</span>
            <span className="flex items-center gap-1 min-w-0">
              {meta && <span className="truncate mr-1">{meta}</span>}
              {maximizable && <>
              <button type="button" className="win-hide" onClick={toggleHalf}
                      aria-pressed={size === 'half'}
                      aria-label={size === 'half' ? `Put ${title} back` : `Dock ${title} to the right half`}
                      title={size === 'half' ? 'Put back (Esc)' : 'Right half of the screen'}>
                <IconHalf />
              </button>
              <button type="button" className="win-hide" onClick={toggleFull}
                      aria-pressed={size === 'full'}
                      aria-label={size === 'full' ? `Leave full screen` : `Show ${title} full screen`}
                      title={size === 'full' ? 'Leave full screen (Esc)' : 'Full screen'}>
                <IconFull on={size === 'full'} />
              </button>
              </>}
              {onHide && (
                <button type="button" className="win-hide" onClick={onHide} aria-label={`Hide ${title}`}>
                  ×
                </button>
              )}
            </span>
          </div>
          <div className={`win-body ${tone} overflow-hidden`} style={height && !out ? { height } : undefined}>
            {children}
          </div>
        </div>
      </section>
    </>
  )
}
