/**
 * Demo mode: the deployed frontend without a backend.
 *
 * On when NEXT_PUBLIC_DEMO_MODE=1, or when a production build has no
 * NEXT_PUBLIC_API_URL (a production page must never call localhost — that is
 * the visitor's machine). API calls then resolve to recorded results instead of
 * the network.
 *
 * The recordings in lib/demo/examples.json are the real pipeline's output, made
 * by `python scripts/build_demo_fixtures.py`: deterministic generator → IR
 * validator and rule engine → ngspice (graded) → PlatformIO compile gate → BOM.
 * Two differences from a live run, both stated in the UI: the requirement was
 * entered through the form producer rather than transcribed by the LLM, and the
 * explanation is the deterministic DerivedExplainer's.
 */

import prompts from './demo/prompts.json'

const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

export const DEMO_MODE =
  process.env.NEXT_PUBLIC_DEMO_MODE === '1' ||
  (!API_URL && process.env.NODE_ENV === 'production')

export const REPO_URL = 'https://github.com/monickverma/cursor-electronics'

export interface DemoExample {
  slug: string
  prompt: string
  requirements: Record<string, unknown>
  generate: Record<string, unknown> & { circuit_id: string; explanation: string }
  simulation: Record<string, unknown> | null
  firmware: Record<string, unknown>
  bom: Record<string, unknown>
}

// The prompts are small and shown at once; the recordings (~450 kB) load on first use.
export const DEMO_PROMPTS: string[] = (prompts as { prompt: string }[]).map(p => p.prompt)

let loaded: Promise<DemoExample[]> | null = null
function examples(): Promise<DemoExample[]> {
  loaded ??= import('./demo/examples.json').then(
    m => (m.default as unknown as { examples: DemoExample[] }).examples,
  )
  return loaded
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

// A prompt is matched to a recording exactly, or by the words that name the
// circuit. Anything else is said plainly: the demo replays, it does not design.
const KEYWORDS: Record<string, string[]> = {
  'rc-lowpass': ['low pass', 'lowpass', 'rc filter', 'cutoff'],
  'voltage-divider': ['divider'],
  'led-indicator': ['led'],
  'rs485-modbus': ['rs485', 'rs 485', 'modbus', 'max485'],
  'room-monitor': ['room monitor', 'dht22', 'buzzer', 'temperature'],
}

function matchExample(all: DemoExample[], prompt: string): DemoExample | undefined {
  const p = norm(prompt)
  const exact = all.find(e => norm(e.prompt) === p)
  if (exact) return exact
  // Room monitor first: its sentence also mentions an LED.
  const order = ['room-monitor', 'rs485-modbus', 'rc-lowpass', 'voltage-divider', 'led-indicator']
  for (const slug of order) {
    if (KEYWORDS[slug].some(k => p.includes(k))) return all.find(e => e.slug === slug)
  }
  return undefined
}

function byCircuit(all: DemoExample[], id: string): DemoExample {
  const e = all.find(x => x.generate.circuit_id === id)
  if (!e) throw new Error('Demo mode: that design is not one of the recorded examples.')
  return e
}

const needsBackend = (what: string) =>
  new Error(
    `Demo mode — ${what} needs the live backend (FastAPI + ngspice + an LLM). ` +
    `The examples here are recorded results. Run Circuit OS locally to try it: ${REPO_URL}#readme`,
  )

const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v))

/** Resolve an API call against the recordings. Mirrors the backend's routes. */
export async function demoRequest<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  // A short pause so the UI's loading states are visible, as they are live.
  await new Promise(r => setTimeout(r, 350))

  if (path === '/health') {
    return { status: 'demo', environment: 'demo', pcb_engine_enabled: false } as T
  }
  if (path === '/auth/login' || path === '/auth/register') {
    return { access_token: 'demo' } as T
  }
  if (method === 'POST' && path === '/design/generate') {
    const prompt = String((body as { prompt?: string })?.prompt ?? '')
    const ex = matchExample(await examples(), prompt)
    if (!ex) {
      throw new Error(
        'Demo mode replays recorded designs; it cannot design a new circuit without the backend. ' +
        'Pick one of the example prompts:\n' +
        DEMO_PROMPTS.map(p => `  - ${p}`).join('\n') +
        `\n\nTo describe your own circuit, run Circuit OS locally: ${REPO_URL}#readme`,
      )
    }
    return clone(ex.generate) as T
  }

  const all = await examples()
  let m = path.match(/^\/design\/([^/]+)\/simulation\/[^/]+$/)
  if (m) {
    const sim = byCircuit(all, m[1]).simulation
    if (!sim) throw new Error('Demo mode: this design has no simulation.')
    return clone(sim) as T
  }
  m = path.match(/^\/design\/([^/]+)\/firmware$/)
  if (m) return clone(byCircuit(all, m[1]).firmware) as T
  m = path.match(/^\/design\/([^/]+)\/bom$/)
  if (m) return clone(byCircuit(all, m[1]).bom) as T
  m = path.match(/^\/design\/([^/]+)\/explanation$/)
  if (m) return { status: 'written', explanation: byCircuit(all, m[1]).generate.explanation, error: null } as T

  if (/^\/design\/[^/]+\/patch$/.test(path)) throw needsBackend('changing a design')
  if (/^\/design\/[^/]+\/sign-off$/.test(path)) throw needsBackend('signing off properties')
  if (path === '/pcb/compile') throw needsBackend('PCB layout')
  throw needsBackend(`${method} ${path}`)
}
