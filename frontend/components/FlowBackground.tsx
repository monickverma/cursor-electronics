'use client'

/**
 * The water behind the desktop: a stable-fluids simulation in WebGL 2, drawn as
 * one-bit dither dots.
 *
 * Pass order, once a frame:
 *   splats → advect velocity → divergence → pressure (Jacobi) → subtract gradient
 *   → advect dye → draw
 *
 * It is decoration and nothing reads it: no design value, claim or verdict comes
 * from here. The canvas hides, and the static dot pattern behind it shows
 * instead, when:
 *   - WebGL 2 or its float render targets are missing;
 *   - the renderer is a software one (no GPU): the simulation would then run on
 *     the CPU and take time from the page it decorates;
 *   - frames stay slow even after the pressure solve has been cut down.
 */

import { useEffect, useRef } from 'react'
import { drainSplats, prefersCalm, pushSplat } from '@/lib/flow'

const GROUND: [number, number, number] = [0x16 / 255, 0x21 / 255, 0x3f / 255]
const INK_LIFT = 0.32          // how far the dots sit above the ground colour
const SIM_W = 160              // velocity grid, cells across
const DYE_W = 640
const PRESSURE_STEPS = 14

const VERT = `#version 300 es
in vec2 p; out vec2 uv;
void main() { uv = p * 0.5 + 0.5; gl_Position = vec4(p, 0.0, 1.0); }`

const HEAD = `#version 300 es
precision highp float; precision highp sampler2D;
in vec2 uv; out vec4 o;
`

const FRAG = {
  advect: `uniform sampler2D uV; uniform sampler2D uS; uniform vec2 texel; uniform float dt; uniform float diss;
void main() { vec2 c = uv - dt * texture(uV, uv).xy * texel; o = diss * texture(uS, c); }`,
  splat: `uniform sampler2D uT; uniform vec2 pt; uniform vec3 val; uniform float rad; uniform float aspect;
void main() { vec2 d = uv - pt; d.x *= aspect; o = vec4(texture(uT, uv).xyz + val * exp(-dot(d, d) / rad), 1.0); }`,
  divergence: `uniform sampler2D uV; uniform vec2 texel;
void main() {
  float L = texture(uV, uv - vec2(texel.x, 0.0)).x; float R = texture(uV, uv + vec2(texel.x, 0.0)).x;
  float B = texture(uV, uv - vec2(0.0, texel.y)).y; float T = texture(uV, uv + vec2(0.0, texel.y)).y;
  o = vec4(0.5 * (R - L + T - B), 0.0, 0.0, 1.0);
}`,
  pressure: `uniform sampler2D uP; uniform sampler2D uD; uniform vec2 texel;
void main() {
  float L = texture(uP, uv - vec2(texel.x, 0.0)).x; float R = texture(uP, uv + vec2(texel.x, 0.0)).x;
  float B = texture(uP, uv - vec2(0.0, texel.y)).x; float T = texture(uP, uv + vec2(0.0, texel.y)).x;
  o = vec4((L + R + B + T - texture(uD, uv).x) * 0.25, 0.0, 0.0, 1.0);
}`,
  gradient: `uniform sampler2D uP; uniform sampler2D uV; uniform vec2 texel;
void main() {
  float L = texture(uP, uv - vec2(texel.x, 0.0)).x; float R = texture(uP, uv + vec2(texel.x, 0.0)).x;
  float B = texture(uP, uv - vec2(0.0, texel.y)).x; float T = texture(uP, uv + vec2(0.0, texel.y)).x;
  o = vec4(texture(uV, uv).xy - 0.5 * vec2(R - L, T - B), 0.0, 1.0);
}`,
  // Dye density against an 8×8 ordered-dither threshold, drawn as round dots.
  show: `uniform sampler2D uS; uniform vec3 ground; uniform vec3 ink; uniform float cell;
float b2(vec2 a) { a = floor(a); return fract(a.x / 2.0 + a.y * a.y * 0.75); }
float b4(vec2 a) { return b2(0.5 * a) * 0.25 + b2(a); }
float b8(vec2 a) { return b4(0.5 * a) * 0.25 + b2(a); }
void main() {
  float d = smoothstep(0.03, 1.0, clamp(texture(uS, uv).x, 0.0, 1.0));
  vec2 c = gl_FragCoord.xy / cell;
  float on = step(b8(c) + 0.04, d) * step(length(fract(c) - 0.5), 0.36);
  o = vec4(mix(ground, ink, on), 1.0);
}`,
}

interface Program { pr: WebGLProgram; u: Record<string, WebGLUniformLocation | null> }
interface Target { tex: WebGLTexture; fbo: WebGLFramebuffer; w: number; h: number }
interface Pair { a: Target; b: Target; swap: () => void }

const SOFTWARE_GL = /swiftshader|llvmpipe|software|basic render/i

function startFluid(canvas: HTMLCanvasElement, giveUp: () => void): (() => void) | null {
  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false })
  if (!gl || !gl.getExtension('EXT_color_buffer_float')) return null
  const info = gl.getExtension('WEBGL_debug_renderer_info')
  const renderer = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : ''
  if (SOFTWARE_GL.test(renderer)) return null

  const owned: { programs: WebGLProgram[]; textures: WebGLTexture[]; fbos: WebGLFramebuffer[] } =
    { programs: [], textures: [], fbos: [] }

  const shader = (type: number, src: string): WebGLShader => {
    const s = gl.createShader(type)!
    gl.shaderSource(s, src)
    gl.compileShader(s)
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'shader')
    return s
  }
  const vs = shader(gl.VERTEX_SHADER, VERT)
  const program = (body: string): Program => {
    const pr = gl.createProgram()!
    gl.attachShader(pr, vs)
    gl.attachShader(pr, shader(gl.FRAGMENT_SHADER, HEAD + body))
    gl.bindAttribLocation(pr, 0, 'p')
    gl.linkProgram(pr)
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr) || 'link')
    const u: Program['u'] = {}
    const n = gl.getProgramParameter(pr, gl.ACTIVE_UNIFORMS) as number
    for (let i = 0; i < n; i++) {
      const name = gl.getActiveUniform(pr, i)!.name
      u[name] = gl.getUniformLocation(pr, name)
    }
    owned.programs.push(pr)
    return { pr, u }
  }

  let P: Record<keyof typeof FRAG, Program>
  try {
    P = {
      advect: program(FRAG.advect), splat: program(FRAG.splat), divergence: program(FRAG.divergence),
      pressure: program(FRAG.pressure), gradient: program(FRAG.gradient), show: program(FRAG.show),
    }
  } catch {
    return null
  }

  const vao = gl.createVertexArray()
  gl.bindVertexArray(vao)
  const quad = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, quad)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
  gl.enableVertexAttribArray(0)
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0)

  const target = (w: number, h: number): Target => {
    const tex = gl.createTexture()!
    gl.bindTexture(gl.TEXTURE_2D, tex)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null)
    const fbo = gl.createFramebuffer()!
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo)
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0)
    gl.viewport(0, 0, w, h)
    gl.clearColor(0, 0, 0, 1)
    gl.clear(gl.COLOR_BUFFER_BIT)
    owned.textures.push(tex)
    owned.fbos.push(fbo)
    return { tex, fbo, w, h }
  }
  const pair = (w: number, h: number): Pair => {
    const d = { a: target(w, h), b: target(w, h) } as Pair
    d.swap = () => { const t = d.a; d.a = d.b; d.b = t }
    return d
  }

  // The grids follow the viewport's shape so a cell stays roughly square.
  let aspect = 1
  let simH = 90
  let vel: Pair, prs: Pair, dye: Pair, div: Target
  const build = () => {
    for (const t of owned.textures) gl.deleteTexture(t)
    for (const f of owned.fbos) gl.deleteFramebuffer(f)
    owned.textures.length = 0
    owned.fbos.length = 0
    aspect = (canvas.clientWidth || 1440) / (canvas.clientHeight || 900)
    simH = Math.max(48, Math.min(260, Math.round(SIM_W / aspect)))
    vel = pair(SIM_W, simH)
    prs = pair(SIM_W, simH)
    div = target(SIM_W, simH)
    dye = pair(DYE_W, Math.max(200, Math.min(1040, Math.round(DYE_W / aspect))))
  }
  build()

  const run = (prog: Program, dst: Target | null, set: (u: Program['u']) => void) => {
    gl.useProgram(prog.pr)
    set(prog.u)
    gl.bindFramebuffer(gl.FRAMEBUFFER, dst ? dst.fbo : null)
    gl.viewport(0, 0, dst ? dst.w : canvas.width, dst ? dst.h : canvas.height)
    gl.drawArrays(gl.TRIANGLES, 0, 3)
  }
  const bind = (unit: number, t: Target): number => {
    gl.activeTexture(gl.TEXTURE0 + unit)
    gl.bindTexture(gl.TEXTURE_2D, t.tex)
    return unit
  }
  const splat = (dst: Pair, x: number, y: number, a: number, b: number, r: number) => {
    run(P.splat, dst.b, (u) => {
      gl.uniform1i(u.uT, bind(0, dst.a))
      gl.uniform2f(u.pt, x, y)
      gl.uniform3f(u.val, a, b, 0)
      gl.uniform1f(u.rad, r)
      gl.uniform1f(u.aspect, aspect)
    })
    dst.swap()
  }

  const calm = prefersCalm()
  const ink: [number, number, number] = [
    GROUND[0] + (1 - GROUND[0]) * INK_LIFT,
    GROUND[1] + (1 - GROUND[1]) * INK_LIFT,
    GROUND[2] + (1 - GROUND[2]) * INK_LIFT,
  ]

  let raf = 0
  let dead = false
  let last = performance.now()
  // A slow machine gets fewer pressure steps first; if that is not enough, no water.
  let slowFrames = 0
  let steps = PRESSURE_STEPS

  const frame = (now: number) => {
    if (dead) return
    raf = requestAnimationFrame(frame)
    const elapsed = now - last
    last = now
    const dt = Math.min(0.033, Math.max(0.001, elapsed / 1000))
    const t = now / 1000

    if (elapsed > 26) slowFrames += 1
    else if (slowFrames > 0) slowFrames -= 1
    if (slowFrames > 90) {
      if (steps > 6) {
        steps = 6
        slowFrames = 0
      } else {
        giveUp()
        return
      }
    }

    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    const cw = Math.round(canvas.clientWidth * dpr)
    const ch = Math.round(canvas.clientHeight * dpr)
    if (!cw || !ch) return
    if (canvas.width !== cw || canvas.height !== ch) {
      canvas.width = cw
      canvas.height = ch
      if (Math.abs(cw / ch - aspect) / aspect > 0.15) build()
    }
    const tx = 1 / SIM_W
    const ty = 1 / simH

    // Three slow emitters keep the water moving when nobody touches it.
    const k = calm ? 0.3 : 1
    for (let i = 0; i < 3; i++) {
      const a = t * (0.21 + i * 0.07) + i * 2.1
      const b = a * 1.31 + i
      const x = 0.5 + 0.38 * Math.sin(a)
      const y = 0.46 + 0.32 * Math.sin(b)
      splat(vel, x, y, Math.cos(a) * 260 * k * dt, Math.cos(b) * 220 * k * dt, 0.006)
      splat(dye, x, y, 1.1 * dt, 0, 0.006)
    }
    for (const s of drainSplats(32)) {
      splat(vel, s.x, s.y, s.dx * SIM_W, s.dy * simH, s.r)
      if (s.dye) splat(dye, s.x, s.y, s.dye, 0, s.r)
    }

    run(P.advect, vel.b, (u) => {
      const unit = bind(0, vel.a)
      gl.uniform1i(u.uV, unit)
      gl.uniform1i(u.uS, unit)
      gl.uniform2f(u.texel, tx, ty)
      gl.uniform1f(u.dt, dt)
      gl.uniform1f(u.diss, Math.exp(-0.25 * dt))
    })
    vel.swap()

    run(P.divergence, div, (u) => {
      gl.uniform1i(u.uV, bind(0, vel.a))
      gl.uniform2f(u.texel, tx, ty)
    })
    for (let i = 0; i < steps; i++) {
      run(P.pressure, prs.b, (u) => {
        gl.uniform1i(u.uP, bind(0, prs.a))
        gl.uniform1i(u.uD, bind(1, div))
        gl.uniform2f(u.texel, tx, ty)
      })
      prs.swap()
    }
    run(P.gradient, vel.b, (u) => {
      gl.uniform1i(u.uP, bind(0, prs.a))
      gl.uniform1i(u.uV, bind(1, vel.a))
      gl.uniform2f(u.texel, tx, ty)
    })
    vel.swap()

    run(P.advect, dye.b, (u) => {
      gl.uniform1i(u.uV, bind(0, vel.a))
      gl.uniform1i(u.uS, bind(1, dye.a))
      gl.uniform2f(u.texel, tx, ty)
      gl.uniform1f(u.dt, dt)
      gl.uniform1f(u.diss, Math.exp(-0.42 * dt))
    })
    dye.swap()

    run(P.show, null, (u) => {
      gl.uniform1i(u.uS, bind(0, dye.a))
      gl.uniform3f(u.ground, GROUND[0], GROUND[1], GROUND[2])
      gl.uniform3f(u.ink, ink[0], ink[1], ink[2])
      gl.uniform1f(u.cell, 5 * dpr)
    })
  }
  raf = requestAnimationFrame(frame)

  return () => {
    dead = true
    cancelAnimationFrame(raf)
    for (const t of owned.textures) gl.deleteTexture(t)
    for (const f of owned.fbos) gl.deleteFramebuffer(f)
    for (const p of owned.programs) gl.deleteProgram(p)
    gl.deleteBuffer(quad)
    gl.deleteVertexArray(vao)
  }
}

export default function FlowBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    let stop: (() => void) | null = null
    const giveUp = () => {
      stop?.()
      stop = null
      canvas.style.display = 'none'
    }
    try {
      stop = startFluid(canvas, giveUp)
    } catch {
      stop = null
    }
    if (!stop) {
      canvas.style.display = 'none'
      return
    }
    canvas.style.display = 'block'

    // The pointer stirs the water wherever it goes, over windows too.
    let lx = 0
    let ly = 0
    let seen = false
    const onMove = (e: PointerEvent) => {
      const w = window.innerWidth || 1
      const h = window.innerHeight || 1
      if (seen) {
        const dx = e.clientX - lx
        const dy = e.clientY - ly
        if (dx || dy) {
          pushSplat({
            x: e.clientX / w,
            y: 1 - e.clientY / h,
            dx: (dx / w) * 30,
            dy: (-dy / h) * 30,
            dye: Math.min(0.6, Math.hypot(dx, dy) * 0.02),
            r: 0.0035,
          })
        }
      }
      lx = e.clientX
      ly = e.clientY
      seen = true
    }
    const onLost = (e: Event) => {
      e.preventDefault()
      giveUp()
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    canvas.addEventListener('webglcontextlost', onLost)

    return () => {
      window.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('webglcontextlost', onLost)
      stop?.()
    }
  }, [])

  return (
    <>
      <div className="flow-fallback" aria-hidden="true" />
      <canvas ref={canvasRef} className="flow-canvas" aria-hidden="true" data-testid="flow-water" />
    </>
  )
}
