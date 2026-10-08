'use client'

/**
 * Board3DView — the board in 3D, drawn from the scene the backend derives from
 * the Board IR (backend/pcb_engine/scene3d.py). Nothing here decides what the
 * board is: every pad, hole, track and body comes from that scene, so the view
 * and the IR cannot disagree. decisions.md [2026-10-06].
 *
 * Browser-only (three.js / WebGL): load it with next/dynamic and ssr: false,
 * exactly like the kicanvas viewer.
 *
 * Rendering is on demand (frameloop="demand"): an idle board draws nothing, and
 * only camera moves, hover and the lift animation request frames.
 *
 * Axes: scene millimetres (x right, y up in the board plane, z out of the top
 * copper) map to three.js as  X = x - w/2,  Y = z,  Z = -(y - h/2).
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { Canvas, ThreeEvent, useFrame, useThree } from '@react-three/fiber'
import { CameraControls, Html, Line } from '@react-three/drei'
import type { BoardScene, SceneComponent, ScenePad } from '@/lib/api'

// ─────────────────────────────────────────────────────────────────────────────
// Coordinates
// ─────────────────────────────────────────────────────────────────────────────
type V3 = [number, number, number]

function makeWorld(w: number, h: number) {
  return (x: number, y: number, z: number): V3 => [x - w / 2, z, -(y - h / 2)]
}

/** A point in a part's own frame (x, y in the board plane, z up) as group-local three.js coords. */
const L = (x: number, y: number, z: number): V3 => [x, z, -y]
/** A box size given as (along x, along y, height). */
const S = (sx: number, sy: number, sz: number): V3 => [sx, sz, sy]

const COPPER_UNDER_MASK = '#2f8f52'
const HOLE = '#0a0a0a'
const SILVER = '#c9ccd1'
const GOLD_PIN = '#d4b26a'

// ─────────────────────────────────────────────────────────────────────────────
// Public component
// ─────────────────────────────────────────────────────────────────────────────
type ViewName = 'iso' | 'top' | 'bottom' | 'front' | 'side'

interface Layers {
  components: boolean
  copper: boolean
  silkscreen: boolean
  ratsnest: boolean
  drc: boolean
}

export default function Board3DView({ scene }: { scene: BoardScene }) {
  const [view, setView] = useState<ViewName>('iso')
  const [viewNonce, setViewNonce] = useState(0)
  const [layers, setLayers] = useState<Layers>({
    components: true, copper: true, silkscreen: true, ratsnest: true, drc: true,
  })
  const [lifted, setLifted] = useState(false)
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  const sel = scene.components.find(c => c.ref === selected) ?? null
  const selPads = useMemo(
    () => (selected ? scene.pads.filter(p => p.ref === selected) : []),
    [scene.pads, selected],
  )

  const go = (v: ViewName) => { setView(v); setViewNonce(n => n + 1) }
  const toggle = (k: keyof Layers) => setLayers(l => ({ ...l, [k]: !l[k] }))

  return (
    <div className="relative w-full h-full min-h-0" data-testid="board-3d">
      <Canvas
        frameloop="demand"
        dpr={[1, 2]}
        gl={{ antialias: true, preserveDrawingBuffer: true }}
        camera={{ fov: 35, near: 0.1, far: 5000, position: [0, 200, 0.001] }}
        onPointerMissed={() => setSelected(null)}
        style={{ background: 'radial-gradient(ellipse at 50% 40%, #2a2a2a 0%, #141414 75%)' }}
      >
        <SceneLights />
        <Board
          scene={scene}
          layers={layers}
          lifted={lifted}
          hovered={hovered}
          selected={selected}
          onHover={setHovered}
          onSelect={setSelected}
        />
        <CameraRig scene={scene} view={view} nonce={viewNonce} />
      </Canvas>

      {/* ── toolbar ── */}
      <div
        className="absolute top-3 left-3 flex flex-wrap gap-1.5 items-center"
        style={{ fontSize: 'var(--body-xs)' }}
      >
        <Group label="View">
          {(['iso', 'top', 'bottom', 'front', 'side'] as ViewName[]).map(v => (
            <ToolButton key={v} active={view === v} onClick={() => go(v)}>
              {v === 'iso' ? '3D' : v[0].toUpperCase() + v.slice(1)}
            </ToolButton>
          ))}
        </Group>
        <Group label="Show">
          {(Object.keys(layers) as (keyof Layers)[]).map(k => (
            <ToolButton key={k} active={layers[k]} onClick={() => toggle(k)}>
              {k === 'drc' ? 'DRC' : k[0].toUpperCase() + k.slice(1)}
            </ToolButton>
          ))}
        </Group>
        <ToolButton active={lifted} onClick={() => setLifted(v => !v)}>
          {lifted ? 'Seat parts' : 'Lift parts'}
        </ToolButton>
      </div>

      {/* ── honesty strip: what this board is not ── */}
      <div
        className="absolute bottom-3 left-3 flex flex-wrap gap-2"
        style={{ fontSize: 'var(--body-xs)' }}
      >
        <Badge tone={scene.stats.unrouted ? 'warn' : 'ok'}>
          {scene.stats.unrouted
            ? `${scene.stats.unrouted} unrouted (dashed)`
            : 'all connections routed'}
        </Badge>
        <Badge tone={scene.stats.drc_errors ? 'bad' : 'ok'}>
          {scene.stats.drc_errors} DRC error{scene.stats.drc_errors === 1 ? '' : 's'}
        </Badge>
        {scene.stats.generic_bodies > 0 && (
          <Badge tone="warn">{scene.stats.generic_bodies} part(s) without a body model (grey box)</Badge>
        )}
        <Badge tone="muted">package-shaped bodies, not manufacturer models · experimental layout</Badge>
      </div>

      {/* ── selection panel ── */}
      {sel && <PartPanel part={sel} pads={selPads} onClose={() => setSelected(null)} />}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Lights and camera
// ─────────────────────────────────────────────────────────────────────────────
function SceneLights() {
  return (
    <>
      <hemisphereLight args={['#f4f1e6', '#1a1d22', 0.85]} />
      <directionalLight position={[60, 120, 80]} intensity={1.6} />
      <directionalLight position={[-80, 60, -60]} intensity={0.45} />
      <directionalLight position={[0, -100, 0]} intensity={0.35} />
    </>
  )
}

function CameraRig({ scene, view, nonce }: { scene: BoardScene; view: ViewName; nonce: number }) {
  const ref = useRef<CameraControls>(null)
  const { w, h } = scene.board
  const span = Math.max(w, h)
  const d = span * 1.55

  useEffect(() => {
    const c = ref.current
    if (!c) return
    const targets: Record<ViewName, V3> = {
      iso: [d * 0.55, d * 0.75, d * 0.75],
      top: [0, d * 1.15, 0.001],
      bottom: [0, -d * 1.15, 0.001],
      front: [0, d * 0.18, d * 1.1],
      side: [d * 1.1, d * 0.18, 0],
    }
    const [x, y, z] = targets[view]
    c.setLookAt(x, y, z, 0, 0, 0, true)
  }, [view, nonce, d])

  return (
    <CameraControls
      ref={ref}
      makeDefault
      smoothTime={0.35}
      minDistance={span * 0.15}
      maxDistance={span * 5}
    />
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// The board
// ─────────────────────────────────────────────────────────────────────────────
interface BoardProps {
  scene: BoardScene
  layers: Layers
  lifted: boolean
  hovered: string | null
  selected: string | null
  onHover: (ref: string | null) => void
  onSelect: (ref: string | null) => void
}

function Board({ scene, layers, lifted, hovered, selected, onHover, onSelect }: BoardProps) {
  const { w, h, thickness: T } = scene.board
  const W = useMemo(() => makeWorld(w, h), [w, h])
  const padsByRef = useMemo(() => {
    const m = new Map<string, ScenePad[]>()
    for (const p of scene.pads) m.set(p.ref, [...(m.get(p.ref) ?? []), p])
    return m
  }, [scene.pads])

  return (
    <group>
      <Substrate scene={scene} />
      {layers.copper && <Copper scene={scene} W={W} />}
      <Pads scene={scene} W={W} />
      <Holes scene={scene} W={W} />
      {layers.silkscreen && <Silkscreen scene={scene} />}
      {layers.components && scene.components.map(c => (
        <Part
          key={c.ref}
          part={c}
          pads={padsByRef.get(c.ref) ?? []}
          W={W}
          T={T}
          lifted={lifted}
          hovered={hovered === c.ref}
          selected={selected === c.ref}
          onHover={onHover}
          onSelect={onSelect}
        />
      ))}
      {layers.ratsnest && scene.ratsnest.map((r, i) => (
        <Line
          key={i}
          points={[W(r.a[0], r.a[1], T + 0.4), W(r.b[0], r.b[1], T + 0.4)]}
          color="#ffd166"
          lineWidth={1.5}
          dashed
          dashSize={0.8}
          gapSize={0.5}
        />
      ))}
      {layers.drc && scene.drc.map((v, i) => (
        <DrcMarker key={i} at={W(v.x, v.y, T + 0.05)} label={`${v.rule}: ${v.detail}`}
                   severity={v.severity} />
      ))}
    </group>
  )
}

function Substrate({ scene }: { scene: BoardScene }) {
  const { w, h, thickness: T, soldermask } = scene.board
  const materials = useMemo(() => {
    const fr4 = new THREE.MeshStandardMaterial({ color: '#c8b67a', roughness: 0.9 })
    const mask = new THREE.MeshStandardMaterial({ color: soldermask, roughness: 0.42, metalness: 0.05 })
    // BoxGeometry face order: +x, -x, +y (top), -y (bottom), +z, -z
    return [fr4, fr4, mask, mask, fr4, fr4]
  }, [soldermask])
  return (
    <mesh position={[0, T / 2, 0]} material={materials}>
      <boxGeometry args={[w, T, h]} />
    </mesh>
  )
}

/** Copper under the soldermask: tracks on both outer layers, as raised lighter green. */
function Copper({ scene, W }: { scene: BoardScene; W: ReturnType<typeof makeWorld> }) {
  const T = scene.board.thickness
  const segs = useMemo(() => {
    const out: { pos: V3; len: number; width: number; angle: number; top: boolean }[] = []
    const joints: { pos: V3; r: number; top: boolean }[] = []
    for (const t of scene.tracks) {
      const top = t.z > 0
      const z = top ? T + 0.02 : -0.02
      for (let i = 0; i < t.points.length - 1; i++) {
        const [x0, y0] = t.points[i]
        const [x1, y1] = t.points[i + 1]
        const len = Math.hypot(x1 - x0, y1 - y0)
        if (len < 1e-6) continue
        out.push({ pos: W((x0 + x1) / 2, (y0 + y1) / 2, z), len, width: t.width,
                   angle: Math.atan2(y1 - y0, x1 - x0), top })
      }
      for (const [x, y] of t.points) joints.push({ pos: W(x, y, z), r: t.width / 2, top })
    }
    return { out, joints }
  }, [scene.tracks, T, W])

  return (
    <group>
      {segs.out.map((s, i) => (
        <mesh key={`s${i}`} position={s.pos} rotation={[0, s.angle, 0]}>
          <boxGeometry args={[s.len, 0.035, s.width]} />
          <meshStandardMaterial color={COPPER_UNDER_MASK} roughness={0.35} />
        </mesh>
      ))}
      {segs.joints.map((j, i) => (
        <mesh key={`j${i}`} position={j.pos}>
          <cylinderGeometry args={[j.r, j.r, 0.035, 16]} />
          <meshStandardMaterial color={COPPER_UNDER_MASK} roughness={0.35} />
        </mesh>
      ))}
    </group>
  )
}

/** Exposed pads: gold finish. Through-hole pads show their ring on both faces. */
function Pads({ scene, W }: { scene: BoardScene; W: ReturnType<typeof makeWorld> }) {
  const { thickness: T, finish } = scene.board
  return (
    <group>
      {scene.pads.map((p, i) => {
        if (p.through) {
          const outer = Math.min(p.w, p.h) / 2
          const inner = (p.drill ?? 0.8) / 2
          return (
            <group key={i}>
              {[T + 0.022, -0.022].map((z, k) => (
                <mesh key={k} position={W(p.x, p.y, z)} rotation={[k ? Math.PI / 2 : -Math.PI / 2, 0, 0]}>
                  <ringGeometry args={[inner, outer, 28]} />
                  <meshStandardMaterial color={finish} metalness={0.85} roughness={0.28}
                                        side={THREE.DoubleSide} />
                </mesh>
              ))}
            </group>
          )
        }
        return (
          <mesh key={i} position={W(p.x, p.y, T + 0.03)}>
            <boxGeometry args={[p.w, 0.04, p.h]} />
            <meshStandardMaterial color={finish} metalness={0.85} roughness={0.28} />
          </mesh>
        )
      })}
      {scene.vias.map((v, i) => (
        <group key={`v${i}`}>
          {[T + 0.022, -0.022].map((z, k) => (
            <mesh key={k} position={W(v.x, v.y, z)} rotation={[k ? Math.PI / 2 : -Math.PI / 2, 0, 0]}>
              <ringGeometry args={[v.drill / 2, v.diameter / 2, 20]} />
              <meshStandardMaterial color={finish} metalness={0.85} roughness={0.28}
                                    side={THREE.DoubleSide} />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  )
}

/** Drilled holes: a dark bore plus a plated barrel through the board. */
function Holes({ scene, W }: { scene: BoardScene; W: ReturnType<typeof makeWorld> }) {
  const T = scene.board.thickness
  return (
    <group>
      {scene.holes.map((hole, i) => (
        <group key={i}>
          {[T + 0.03, -0.03].map((z, k) => (
            <mesh key={k} position={W(hole.x, hole.y, z)} rotation={[k ? Math.PI / 2 : -Math.PI / 2, 0, 0]}>
              <circleGeometry args={[hole.d / 2, 24]} />
              <meshBasicMaterial color={HOLE} side={THREE.DoubleSide} />
            </mesh>
          ))}
          <mesh position={W(hole.x, hole.y, T / 2)}>
            <cylinderGeometry args={[hole.d / 2, hole.d / 2, T + 0.04, 24, 1, true]} />
            <meshStandardMaterial color={GOLD_PIN} metalness={0.8} roughness={0.35}
                                  side={THREE.BackSide} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

/** Reference designators and part outlines, painted once into a texture on the top mask. */
function Silkscreen({ scene }: { scene: BoardScene }) {
  const { w, h, thickness: T, silkscreen } = scene.board
  const texture = useMemo(() => {
    const ppm = Math.min(24, 4096 / Math.max(w, h))     // pixels per millimetre
    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(w * ppm)
    canvas.height = Math.ceil(h * ppm)
    const g = canvas.getContext('2d')!
    g.clearRect(0, 0, canvas.width, canvas.height)
    g.strokeStyle = silkscreen
    g.fillStyle = silkscreen
    g.lineWidth = Math.max(1, 0.15 * ppm)
    const P = (x: number, y: number): [number, number] => [x * ppm, (h - y) * ppm]

    for (const c of scene.components) {
      if (c.side !== 'top') continue
      const [cw, ch] = c.courtyard
      const [cx, cy] = P(c.x, c.y)
      g.save()
      g.translate(cx, cy)
      g.rotate((-c.rotation * Math.PI) / 180)
      g.strokeRect((-cw / 2) * ppm, (-ch / 2) * ppm, cw * ppm, ch * ppm)
      g.restore()
      const size = Math.max(0.9, Math.min(1.6, Math.min(cw, ch) * 0.45)) * ppm
      g.font = `600 ${size}px "JetBrains Mono", monospace`
      g.textAlign = 'center'
      g.textBaseline = 'bottom'
      g.fillText(c.ref, cx, cy - (ch / 2) * ppm - 0.25 * ppm)
    }
    // pin-1 dots
    for (const p of scene.pads) {
      if (p.pin !== '1') continue
      const part = scene.components.find(c => c.ref === p.ref)
      if (!part || part.pins < 3 || part.side !== 'top') continue
      const [x, y] = P(p.x, p.y)
      const off = (Math.max(p.w, p.h) / 2 + 0.5) * ppm
      g.beginPath()
      g.arc(x - off, y, 0.3 * ppm, 0, Math.PI * 2)
      g.fill()
    }
    const t = new THREE.CanvasTexture(canvas)
    t.anisotropy = 8
    t.colorSpace = THREE.SRGBColorSpace
    return t
  }, [scene.components, scene.pads, w, h, silkscreen])

  useEffect(() => () => texture.dispose(), [texture])

  return (
    <mesh position={[0, T + 0.026, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[w, h]} />
      <meshStandardMaterial map={texture} transparent depthWrite={false} roughness={0.8} />
    </mesh>
  )
}

function DrcMarker({ at, label, severity }: { at: V3; label: string; severity: string }) {
  const [hover, setHover] = useState(false)
  const color = severity === 'error' ? '#ef4444' : '#f59e0b'
  return (
    <group position={at}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}
            onPointerOver={e => { e.stopPropagation(); setHover(true) }}
            onPointerOut={() => setHover(false)}>
        <ringGeometry args={[0.55, 0.85, 32]} />
        <meshBasicMaterial color={color} side={THREE.DoubleSide} transparent opacity={0.9} />
      </mesh>
      {hover && (
        <Html center distanceFactor={60} style={{ pointerEvents: 'none' }}>
          <div style={tooltipStyle(color)}>{label}</div>
        </Html>
      )}
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// A component: body from its package, leads to its own pads
// ─────────────────────────────────────────────────────────────────────────────
interface PartProps {
  part: SceneComponent
  pads: ScenePad[]
  W: ReturnType<typeof makeWorld>
  T: number
  lifted: boolean
  hovered: boolean
  selected: boolean
  onHover: (ref: string | null) => void
  onSelect: (ref: string | null) => void
}

function Part({ part, pads, W, T, lifted, hovered, selected, onHover, onSelect }: PartProps) {
  const group = useRef<THREE.Group>(null)
  const invalidate = useThree(s => s.invalidate)
  const lift = lifted ? Math.max(4, part.body.size[2] * 0.8) : 0
  const top = part.side === 'top'
  const baseY = top ? T : 0

  // Spring the part toward its target height; frames are requested only while it moves.
  useFrame((_, dt) => {
    const g = group.current
    if (!g) return
    const target = lift
    const dy = target - g.userData.lift
    if (Math.abs(dy) < 0.005) {
      if (g.userData.lift !== target) { g.userData.lift = target; g.position.y = baseY + target }
      return
    }
    g.userData.lift += dy * Math.min(1, dt * 9)
    g.position.y = baseY + g.userData.lift
    invalidate()
  })
  useEffect(() => { invalidate() }, [lifted, invalidate])

  const [wx, , wz] = W(part.x, part.y, 0)
  const theta = (part.rotation * Math.PI) / 180

  // pads in the part's own (unrotated) frame
  const local = useMemo(() => pads.map(p => {
    const dx = p.x - part.x, dy = p.y - part.y
    const c = Math.cos(-theta), s = Math.sin(-theta)
    return { ...p, lx: dx * c - dy * s, ly: dx * s + dy * c }
  }), [pads, part.x, part.y, theta])

  const emissive = selected ? '#5b4a8a' : hovered ? '#3a3a3a' : '#000000'

  return (
    <group
      ref={group}
      position={[wx, baseY, wz]}
      rotation={[top ? 0 : Math.PI, theta, 0]}
      userData={{ lift: 0 }}
      onPointerOver={(e: ThreeEvent<PointerEvent>) => {
        e.stopPropagation(); onHover(part.ref); document.body.style.cursor = 'pointer'
      }}
      onPointerOut={() => { onHover(null); document.body.style.cursor = '' }}
      onClick={(e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); onSelect(part.ref) }}
    >
      <Body part={part} pads={local} emissive={emissive} />
      {(hovered || selected) && (
        <Html position={L(0, 0, part.body.standoff + part.body.size[2] + 1.2)} center
              distanceFactor={70} style={{ pointerEvents: 'none' }}>
          <div style={tooltipStyle('#f0d7ff')}>
            <strong>{part.ref}</strong> · {part.package ?? '—'} · {part.kind}
            {part.model === 'generic' && <span style={{ color: '#fbbf24' }}> · no body model</span>}
          </div>
        </Html>
      )}
    </group>
  )
}

type LocalPad = ScenePad & { lx: number; ly: number }

function Mat({ color, emissive = '#000000', metal = 0, rough = 0.55, opacity = 1 }:
  { color: string; emissive?: string; metal?: number; rough?: number; opacity?: number }) {
  return (
    <meshStandardMaterial color={color} emissive={emissive} metalness={metal} roughness={rough}
                          transparent={opacity < 1} opacity={opacity} />
  )
}

function Box({ at, size, color, emissive, metal, rough, opacity }:
  { at: V3; size: V3; color: string; emissive?: string; metal?: number; rough?: number; opacity?: number }) {
  return (
    <mesh position={at}>
      <boxGeometry args={size} />
      <Mat color={color} emissive={emissive} metal={metal} rough={rough} opacity={opacity} />
    </mesh>
  )
}

/** Vertical lead from the body down through the board (through-hole parts). */
function ThLeads({ pads, from, extra = 1.2, size = 0.5, color = SILVER, T = 1.6 }:
  { pads: LocalPad[]; from: number; extra?: number; size?: number; color?: string; T?: number }) {
  const len = from + T + extra
  return (
    <>
      {pads.map((p, i) => (
        <Box key={i} at={L(p.lx, p.ly, from - len / 2)} size={S(size, size, len)}
             color={color} metal={0.9} rough={0.3} />
      ))}
    </>
  )
}

function Body({ part, pads, emissive }:
  { part: SceneComponent; pads: LocalPad[]; emissive: string }) {
  const b = part.body
  const [sx, sy, sz] = b.size
  const z0 = b.standoff
  const zc = z0 + sz / 2
  const str = (k: string, d: string) => (typeof b[k] === 'string' ? (b[k] as string) : d)
  const num = (k: string, d: number) => (typeof b[k] === 'number' ? (b[k] as number) : d)

  switch (b.shape) {
    case 'chip': {
      const tl = num('terminal_len', sx * 0.2)
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx - 2 * tl, sy, sz)} color={b.color} emissive={emissive} />
          {[-1, 1].map(s => (
            <Box key={s} at={L(s * (sx / 2 - tl / 2), 0, zc)} size={S(tl, sy, sz)}
                 color={str('terminal_color', SILVER)} metal={0.85} rough={0.3} emissive={emissive} />
          ))}
        </>
      )
    }
    case 'chip_led':
      return (
        <>
          <Box at={L(0, 0, z0 + sz * 0.3)} size={S(sx, sy, sz * 0.6)} color={b.color} emissive={emissive} />
          <Box at={L(0, 0, z0 + sz * 0.8)} size={S(sx * 0.85, sy * 0.85, sz * 0.4)}
               color={str('lens_color', '#e0282e')} opacity={0.85} rough={0.1} emissive={emissive} />
        </>
      )
    case 'sod': {
      const bc = str('band_color', SILVER)
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} />
          <Box at={L(-sx / 2 + 0.35, 0, z0 + sz + 0.005)} size={S(0.35, sy * 0.98, 0.01)} color={bc} />
          {pads.map((p, i) => (
            <Box key={i} at={L(p.lx, p.ly, 0.08)} size={S(Math.min(p.w, 1.0), Math.min(p.h, 0.7), 0.16)}
                 color={str('terminal_color', SILVER)} metal={0.85} rough={0.3} />
          ))}
        </>
      )
    }
    case 'gullwing':
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} rough={0.7} />
          {b.pin1_mark && pads.find(p => p.pin === '1') && (() => {
            const p1 = pads.find(p => p.pin === '1')!
            return (
              <mesh position={L(Math.sign(p1.lx) * (sx / 2 - 0.6), Math.sign(p1.ly) * (sy / 2 - 0.6), z0 + sz + 0.01)}
                    rotation={[-Math.PI / 2, 0, 0]}>
                <circleGeometry args={[0.3, 16]} />
                <meshStandardMaterial color="#3a3a3a" />
              </mesh>
            )
          })()}
          {pads.map((p, i) => {
            // a lead from the body edge out to the pad, low over the board
            const toX = Math.abs(p.lx) > sx / 2 ? Math.sign(p.lx) * sx / 2 : p.lx
            const toY = Math.abs(p.ly) > sy / 2 ? Math.sign(p.ly) * sy / 2 : p.ly
            const mx = (p.lx + toX) / 2, my = (p.ly + toY) / 2
            const lx = Math.max(0.35, Math.abs(p.lx - toX)), ly = Math.max(0.35, Math.abs(p.ly - toY))
            const thin = Math.abs(p.lx - toX) > Math.abs(p.ly - toY)
            return (
              <Box key={i} at={L(mx, my, 0.12)} size={S(thin ? lx : 0.4, thin ? 0.4 : ly, 0.15)}
                   color={SILVER} metal={0.9} rough={0.3} />
            )
          })}
        </>
      )
    case 'dip': {
      const p1 = pads.find(p => p.pin === '1')
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} rough={0.75} />
          {p1 && (
            <mesh position={L(0, Math.sign(p1.ly) * (sy / 2), z0 + sz + 0.01)} rotation={[-Math.PI / 2, 0, 0]}>
              <circleGeometry args={[0.9, 24, 0, Math.PI]} />
              <meshStandardMaterial color="#0d0d0d" />
            </mesh>
          )}
          {pads.map((p, i) => (
            // the bent shoulder from the body side to the pin row
            <Box key={`s${i}`} at={L((p.lx + Math.sign(p.lx) * sx / 2) / 2, p.ly, z0 + 0.6)}
                 size={S(Math.abs(p.lx) - sx / 2 + 0.3, 0.5, 0.25)} color={SILVER} metal={0.9} rough={0.3} />
          ))}
          <ThLeads pads={pads} from={z0 + 0.6} size={0.45} />
        </>
      )
    }
    case 'to92':
      return (
        <>
          <mesh position={L(0, 0, zc)} rotation={[0, 0, 0]}>
            <cylinderGeometry args={[sx / 2, sx / 2, sz, 32, 1, false, 0, Math.PI]} />
            <Mat color={b.color} emissive={emissive} rough={0.7} />
          </mesh>
          <Box at={L(0, -0.01, zc)} size={S(sx, 0.02, sz)} color={b.color} emissive={emissive} rough={0.7} />
          <ThLeads pads={pads} from={z0} size={0.45} />
        </>
      )
    case 'to220':
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} rough={0.7} />
          <Box at={L(0, sy / 2 + 0.65, zc + sz * 0.35)} size={S(sx, 1.3, sz * 1.7)}
               color={str('tab_color', SILVER)} metal={0.9} rough={0.3} />
          <ThLeads pads={pads} from={z0} />
        </>
      )
    case 'axial': {
      const r = sy / 2
      return (
        <>
          <mesh position={L(0, 0, z0 + r)} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[r, r, sx, 28]} />
            <Mat color={b.color} emissive={emissive} rough={0.6} />
          </mesh>
          <mesh position={L(-sx / 2 + 0.6, 0, z0 + r)} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[r * 1.01, r * 1.01, 0.5, 28]} />
            <Mat color={str('band_color', SILVER)} />
          </mesh>
          {pads.map((p, i) => {
            // horizontal lead from the body end to above the pad, then down
            const end = Math.sign(p.lx) * sx / 2
            return (
              <group key={i}>
                <Box at={L((p.lx + end) / 2, 0, z0 + r)} size={S(Math.abs(p.lx - end), 0.5, 0.5)}
                     color={SILVER} metal={0.9} rough={0.3} />
              </group>
            )
          })}
          <ThLeads pads={pads} from={z0 + r} />
        </>
      )
    }
    case 'radial_can':
      return (
        <>
          <mesh position={L(0, 0, zc)}>
            <cylinderGeometry args={[sx / 2, sx / 2, sz, 36]} />
            <Mat color={b.color} emissive={emissive} rough={0.35} />
          </mesh>
          <mesh position={L(0, 0, z0 + sz + 0.01)} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[sx / 2 - 0.2, 36]} />
            <meshStandardMaterial color={SILVER} metalness={0.8} roughness={0.3} />
          </mesh>
          <ThLeads pads={pads} from={z0} />
        </>
      )
    case 'radial_disc':
      return (
        <>
          <mesh position={L(0, 0, zc)} rotation={[Math.PI / 2, 0, 0]} scale={[1, sy / sx, 1]}>
            <cylinderGeometry args={[sx / 2, sx / 2, sy, 32]} />
            <Mat color={b.color} emissive={emissive} rough={0.5} />
          </mesh>
          <ThLeads pads={pads} from={z0} />
        </>
      )
    case 'dht':
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} rough={0.8} />
          {/* the grille on the front face */}
          {Array.from({ length: 6 }).map((_, i) => (
            <Box key={i} at={L(-sx / 2 - 0.01, 0, z0 + sz * 0.3 + i * sz * 0.1)}
                 size={S(0.04, sy * 0.7, sz * 0.045)} color="#bdbdb6" />
          ))}
          <ThLeads pads={pads} from={z0} size={0.5} />
        </>
      )
    case 'header':
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} rough={0.7} />
          {pads.map((p, i) => {
            const pin = num('pin_len', 6)
            return (
              <Box key={i} at={L(p.lx, p.ly, sz + pin / 2 - 1)} size={S(0.64, 0.64, pin)}
                   color={GOLD_PIN} metal={0.9} rough={0.25} />
            )
          })}
          <ThLeads pads={pads} from={0} size={0.64} color={GOLD_PIN} />
        </>
      )
    default: // 'box' and generic
      return (
        <>
          <Box at={L(0, 0, zc)} size={S(sx, sy, sz)} color={b.color} emissive={emissive} rough={0.6}
               opacity={part.model === 'generic' ? 0.75 : 1} />
          {pads.some(p => p.through) && <ThLeads pads={pads.filter(p => p.through)} from={z0} />}
        </>
      )
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Overlay UI
// ─────────────────────────────────────────────────────────────────────────────
function PartPanel({ part, pads, onClose }: { part: SceneComponent; pads: ScenePad[]; onClose: () => void }) {
  return (
    <div
      className="absolute top-14 right-3 w-72 rounded-md border border-border-dark"
      style={{ background: 'rgba(20,20,20,0.94)', color: 'var(--lumen)', fontSize: 'var(--body-xs)',
               backdropFilter: 'blur(6px)' }}
      data-testid="part-panel"
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-dark">
        <div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--body-md)' }}>{part.ref}</span>
          <span style={{ color: 'var(--text-muted-dark)', marginLeft: 8 }}>{part.kind}</span>
        </div>
        <button onClick={onClose} aria-label="Close" style={{ color: 'var(--text-muted-dark)' }}>✕</button>
      </div>
      <dl className="px-3 py-2 grid grid-cols-[6rem_1fr] gap-y-1">
        <dt style={{ color: 'var(--text-muted-dark)' }}>Part</dt><dd>{part.mpn ?? '—'}</dd>
        <dt style={{ color: 'var(--text-muted-dark)' }}>Package</dt><dd>{part.package ?? '—'}</dd>
        <dt style={{ color: 'var(--text-muted-dark)' }}>Position</dt>
        <dd style={{ fontFamily: 'var(--font-mono)' }}>
          {part.x.toFixed(2)}, {part.y.toFixed(2)} mm · {part.rotation}° · {part.side}
        </dd>
        <dt style={{ color: 'var(--text-muted-dark)' }}>3D body</dt>
        <dd style={{ color: part.model === 'generic' ? '#fbbf24' : undefined }}>
          {part.model === 'generic' ? 'none for this package — courtyard box' : 'package-shaped'}
        </dd>
      </dl>
      <div className="px-3 pb-3">
        <div style={{ color: 'var(--text-muted-dark)', marginBottom: 4 }}>Pins</div>
        <div className="max-h-40 overflow-auto" style={{ fontFamily: 'var(--font-mono)' }}>
          {pads.map(p => (
            <div key={p.pin} className="flex justify-between">
              <span>{p.pin}</span>
              <span style={{ color: p.net ? 'var(--dawn)' : 'var(--text-muted-dark)' }}>{p.net || 'no net'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1 rounded-md px-1.5 py-1"
         style={{ background: 'rgba(20,20,20,0.85)', border: '1px solid var(--border-dark)' }}>
      <span style={{ color: 'var(--text-muted-dark)', marginRight: 2 }}>{label}</span>
      {children}
    </div>
  )
}

function ToolButton({ active, onClick, children }:
  { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className="rounded px-2 py-0.5 transition-colors"
      style={{
        background: active ? 'var(--dawn)' : 'transparent',
        color: active ? 'var(--vast)' : 'var(--lumen-dim)',
        border: active ? '1px solid var(--dawn)' : '1px solid var(--border-dark)',
      }}
    >
      {children}
    </button>
  )
}

function Badge({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'muted'; children: React.ReactNode }) {
  const colors = {
    ok: ['#12261a', '#4ade80'], warn: ['#2a2214', '#fbbf24'],
    bad: ['#281515', '#f87171'], muted: ['rgba(20,20,20,0.85)', '#888888'],
  }[tone]
  return (
    <span className="rounded px-2 py-0.5"
          style={{ background: colors[0], color: colors[1], border: '1px solid var(--border-dark)' }}>
      {children}
    </span>
  )
}

function tooltipStyle(accent: string): React.CSSProperties {
  return {
    background: 'rgba(20,20,20,0.92)', color: 'var(--lumen)', border: `1px solid ${accent}`,
    borderRadius: 6, padding: '3px 8px', whiteSpace: 'nowrap', fontSize: 12,
    fontFamily: 'var(--font-body)',
  }
}
