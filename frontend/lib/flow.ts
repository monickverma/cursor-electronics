/**
 * The water behind the desktop is one fluid simulation (FlowBackground). Anything
 * that moves — the pointer, a window being thrown — stirs it by pushing a splat
 * here; the simulation drains the queue once a frame.
 *
 * All coordinates are fractions of the viewport, y up, so a caller never needs
 * to know the simulation's grid.
 */
export interface Splat {
  x: number      // 0 left … 1 right
  y: number      // 0 bottom … 1 top
  dx: number     // impulse, in viewport widths
  dy: number     // impulse, in viewport heights (up is positive)
  dye: number    // how much ink it leaves, 0 … ~1
  r: number      // radius² of the gaussian, in viewport-width units
}

const MAX_QUEUED = 64
const queue: Splat[] = []

export function pushSplat(s: Splat): void {
  if (queue.length < MAX_QUEUED) queue.push(s)
}

/** Take up to `max` splats; whatever is left over is dropped, not carried forward. */
export function drainSplats(max = 32): Splat[] {
  const taken = queue.splice(0, max)
  queue.length = 0
  return taken
}

/**
 * Sent on `window` when a FloatWindow leaves the layout: docked beside the library
 * (`half`) or full screen. Any other window out goes back; the page opens the library
 * for a dock, so the design list is on the left and the window on the right.
 */
export const WINDOW_OUT = 'flow:window-out'
export interface WindowOut { id: string; size: 'half' | 'full' }

// Windows stack in the order they were last touched.
let z = 10
export function nextZ(): number {
  z += 1
  return z
}

export function prefersCalm(): boolean {
  return typeof window !== 'undefined'
    && !!window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
