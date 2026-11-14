'use client'

/**
 * The requirement console (spec §6). A transcript, not chat bubbles: the user's lines behind a `>`
 * prompt, the system's entries under a lettered tag (GENERATED, PATCHED, NEEDS INPUT, REFUSED, ERROR)
 * with a timestamp. The explanation is not pasted here: it lives on the Overview sheet.
 *
 * Without a token it renders the sign-in form (the shell wraps it in the `Account` card).
 */
import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { generateDesign, patchDesign, login, register, UnderdeterminedError, GenerateResponse, PatchResponse } from '@/lib/api'
import { DEMO_MODE, DEMO_PROMPTS } from '@/lib/demo'
import { Button, Callout, Cursor, Field, Input, Textarea } from '@/components/ui'

type Entry =
  | { kind: 'user'; text: string; at: Date }
  | { kind: 'generated'; at: Date; applicationClass: string; targetMcu: string | null; version: number; writing: boolean }
  | { kind: 'patched'; at: Date; changes: string[]; predictDelta: string[]; generatorChanged: { from: string; to: string } | null; version: number; note: string }
  | { kind: 'needs_input'; at: Date; text: string }
  | { kind: 'refused'; at: Date; text: string }
  | { kind: 'error'; at: Date; text: string }

interface Props {
  onResult: (res: GenerateResponse | PatchResponse) => void
  token: string
  onTokenChange: (t: string) => void
  currentCircuitId?: string
}

type AuthMode = 'login' | 'register'

// The prefix lib/api.ts writes for an `out_of_envelope` refusal — the one refusal the client can tell apart.
const REFUSAL_PREFIX = 'No generator accepts that requirement:'

export default function ChatPanel({ onResult, token, onTokenChange, currentCircuitId }: Props) {
  const [messages, setMessages] = useState<Entry[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  // What the running request is doing, for the status line.
  const [working, setWorking] = useState('')
  // The request the system asked about. Held until it is answered, so the reply is added to it.
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('test@circuitos.dev')
  const [password, setPassword] = useState('TestPass123!')
  const [authError, setAuthError] = useState('')
  const [examplesOpen, setExamplesOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  // An entry added while the panel was hidden (the drawer on a narrow screen) could not be scrolled
  // to; scroll to the newest entry again when the transcript becomes visible.
  useEffect(() => {
    const el = logRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    let wasHidden = el.clientHeight === 0
    const ro = new ResizeObserver(() => {
      const hidden = el.clientHeight === 0
      if (wasHidden && !hidden) el.scrollTop = el.scrollHeight
      wasHidden = hidden
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [token])

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [input])

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault()
    setAuthError('')
    try {
      const res = authMode === 'login'
        ? await login(email, password)
        : await register(email, password)
      onTokenChange(res.access_token)
    } catch (err: unknown) {
      setAuthError(err instanceof Error ? err.message : 'Auth failed')
    }
  }

  async function handleSend(override?: string) {
    const text = (override ?? input).trim()
    if (!text || loading) return
    setInput('')
    setExamplesOpen(false)
    setMessages(prev => [...prev, { kind: 'user', text, at: new Date() }])
    setLoading(true)
    try {
      let res: GenerateResponse | PatchResponse
      if (currentCircuitId && messages.length > 0 && !DEMO_MODE) {
        setWorking('Applying the change to the requirement')
        res = await patchDesign(currentCircuitId, text, token)
        const p = res as PatchResponse
        setMessages(prev => [...prev, {
          kind: 'patched', at: new Date(), changes: p.changes, predictDelta: p.predict_delta ?? [],
          generatorChanged: p.generator_changed ?? null, version: p.version,
          note: p.note_to_user || 'No changes applied.',
        }])
      } else {
        setWorking(DEMO_MODE ? 'Opening the recording' : 'Compiling the requirement')
        const prompt = pendingPrompt ? `${pendingPrompt}. ${text}` : text
        res = await generateDesign(prompt, token)
        setPendingPrompt(null)
        const g = res as GenerateResponse
        setMessages(prev => [...prev, {
          kind: 'generated', at: new Date(), applicationClass: g.application_class, targetMcu: g.target_mcu,
          version: g.version, writing: !g.explanation && g.explanation_status === 'writing',
        }])
      }
      onResult(res)
    } catch (err: unknown) {
      if (err instanceof UnderdeterminedError) setPendingPrompt(pendingPrompt ? `${pendingPrompt}. ${text}` : text)
      const msg = err instanceof Error ? err.message : 'Unknown error'
      const kind = err instanceof UnderdeterminedError ? 'needs_input'
        : msg.startsWith(REFUSAL_PREFIX) ? 'refused'
        : 'error'
      setMessages(prev => [...prev, { kind, text: msg, at: new Date() }])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  function pickExample(ex: string) {
    // In demo mode an example is a recording: open it at once. Live, it fills the composer.
    if (DEMO_MODE) handleSend(ex)
    else { setInput(ex); setExamplesOpen(false); textareaRef.current?.focus() }
  }

  /* ── Sign-in ───────────────────────────────────────────────── */
  if (!token) {
    const login_ = authMode === 'login'
    return (
      <div className="flex flex-1 flex-col gap-[24px] p-[16px]">
        <div className="flex flex-col gap-[4px]">
          <h2 className="t-title">{login_ ? 'Sign in to the workbench' : 'Create an account'}</h2>
          <p className="t-small c-fg-2">
            {login_ ? 'Your designs and their revisions are kept with your account.' : 'An email address and a password are all it takes.'}
          </p>
        </div>
        <form onSubmit={handleAuth} className="flex flex-col gap-[16px]">
          <Field label="Email">
            <Input
              type="email"
              placeholder="Email address"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              placeholder="Password"
              autoComplete={login_ ? 'current-password' : 'new-password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </Field>
          {authError && <Callout tone="fail" role="alert" title={login_ ? 'Sign-in failed' : 'Could not create the account'}>{authError}</Callout>}
          <Button type="submit" variant="primary" size="lg" className="w-full">
            {login_ ? 'Sign in' : 'Create account'}
          </Button>
        </form>
        <p className="t-small c-fg-3 mt-auto">
          {login_ ? 'No account? ' : 'Have an account? '}
          <button
            type="button"
            className="link t-small"
            onClick={() => { setAuthMode(m => m === 'login' ? 'register' : 'login'); setAuthError('') }}
          >
            {login_ ? 'Register' : 'Back to sign in'}
          </button>
        </p>
      </div>
    )
  }

  /* ── Console ───────────────────────────────────────────────── */
  const empty = messages.length === 0
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={logRef} className="min-h-0 flex-1 overflow-y-auto" role="log" aria-label="Requirement transcript">
        {empty && (
          <div className="pb-[16px] pt-[16px]">
            <p className="t-label px-[16px]">{DEMO_MODE ? 'Recorded examples' : 'Examples'}</p>
            <p className="t-small c-fg-3 mt-[8px] px-[16px]">
              {DEMO_MODE ? 'Each opens a recorded design.' : 'Pick one to start from, or describe your own circuit below.'}
            </p>
            <ol className="mt-[12px] border-t border-line">
              {EXAMPLES.map((ex, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => pickExample(ex)}
                    disabled={loading}
                    className="flex w-full items-baseline gap-[12px] border-b border-line px-[16px] py-[8px] text-left text-fg-2 transition-colors duration-ui hover:bg-bench-3 hover:text-fg disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="t-data c-fg-3 flex-none">{String(i + 1).padStart(2, '0')}</span>
                    <span className="t-ui">{ex}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        )}

        {messages.map((m, i) => <EntryView key={i} entry={m} />)}

        {loading && (
          <div className="border-b border-line px-[16px] py-[12px]" role="status">
            <span className="t-small c-fg-2 mr-[6px]">{working}</span><Cursor label="working" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="flex-none border-t border-line">
        {!empty && (
          <div className="border-b border-line">
            <button
              type="button"
              className="disclosure h-row px-[16px] hover:text-fg"
              aria-expanded={examplesOpen}
              aria-controls="req-examples"
              onClick={() => setExamplesOpen(o => !o)}
            >
              {examplesOpen ? <ChevronDown size={12} strokeWidth={1.5} aria-hidden /> : <ChevronRight size={12} strokeWidth={1.5} aria-hidden />}
              <span className="t-label">Examples</span>
              <span className="t-data c-fg-3" style={{ fontSize: 11 }}>{EXAMPLES.length}</span>
            </button>
            {examplesOpen && (
              <ol id="req-examples" className="max-h-[192px] overflow-y-auto border-t border-line pb-[4px]">
                {EXAMPLES.map((ex, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      onClick={() => pickExample(ex)}
                      disabled={loading}
                      title={ex}
                      className="flex h-row w-full items-center gap-[12px] px-[16px] text-left text-fg-2 transition-colors duration-ui hover:bg-bench-3 hover:text-fg disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <span className="t-data c-fg-3 flex-none">{String(i + 1).padStart(2, '0')}</span>
                      <span className="t-small truncate-1">{ex}</span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}

        <div className="px-[16px] py-[12px]">
          {pendingPrompt && (
            <div className="mb-[8px] flex items-baseline gap-[8px]" role="note">
              <span className="t-label flex-none">Your reply is added to</span>
              <span className="t-small c-fg-2 truncate-1" title={pendingPrompt}>{pendingPrompt}</span>
            </div>
          )}
          <div className="flex items-end gap-[8px]">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={DEMO_MODE ? 'Pick a recorded example…' : currentCircuitId ? 'Request a change…' : 'Describe your circuit…'}
              aria-label={pendingPrompt ? 'Answer the open questions' : currentCircuitId ? 'Request a change' : 'Describe your circuit'}
              rows={1}
              disabled={loading}
              className="flex-1"
              style={{ minHeight: 36 }}
            />
            <Button variant="primary" size="lg" onClick={() => handleSend()} disabled={loading || !input.trim()}>
              Send
            </Button>
          </div>
          <p className="t-label mt-[8px] whitespace-nowrap">Enter ↵ send · Shift+Enter newline</p>
        </div>
      </div>
    </div>
  )
}

/* ── Entries ──────────────────────────────────────────────────── */

const TAG: Record<Exclude<Entry['kind'], 'user'>, string> = {
  generated: 'Generated',
  patched: 'Patched',
  needs_input: 'Needs input',
  refused: 'Refused',
  error: 'Error',
}

function time(d: Date) {
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

function EntryView({ entry: e }: { entry: Entry }) {
  if (e.kind === 'user') {
    return (
      <div className="flex gap-[8px] border-b border-line px-[16px] py-[12px]">
        <span className="t-data c-fg-3 flex-none" aria-hidden="true">&gt;</span>
        <p className="t-ui c-fg min-w-0 whitespace-pre-wrap" style={{ overflowWrap: 'anywhere' }}>{e.text}</p>
      </div>
    )
  }
  const rev = e.kind === 'generated' || (e.kind === 'patched' && e.changes.length > 0) ? `v${e.version}` : null
  return (
    <div className="border-b border-line px-[16px] py-[12px] fade-in">
      <div className="mb-[8px] flex items-center gap-[12px]">
        <span className="t-label">{TAG[e.kind]}</span>
        <time className="t-data c-fg-3" style={{ fontSize: 11 }} dateTime={e.at.toISOString()}>{time(e.at)}</time>
        {rev && <span className="t-data c-fg-2 ml-auto" style={{ fontSize: 11 }}>REV {rev}</span>}
      </div>
      <EntryBody entry={e} />
    </div>
  )
}

function EntryBody({ entry: e }: { entry: Exclude<Entry, { kind: 'user' }> }) {
  switch (e.kind) {
    case 'generated':
      return (
        <div className="t-ui c-fg-2 flex flex-col gap-[4px]">
          <p>
            Built <span className="t-data c-fg">{e.applicationClass}</span>
            {e.targetMcu && <> on <span className="t-data c-fg">{e.targetMcu}</span></>}, revision{' '}
            <span className="t-data c-fg">v{e.version}</span>.
          </p>
          <p>
            The compile report is on the Overview sheet.
            {e.writing && ' Its explanation is still being written.'}
          </p>
        </div>
      )
    case 'patched':
      if (e.changes.length === 0) return <p className="t-ui c-fg-2">{e.note}</p>
      return (
        <div className="flex flex-col gap-[8px]">
          <ul className="t-data c-fg" style={{ overflowWrap: 'anywhere' }}>
            {e.changes.map((c, i) => <li key={i}>{c}</li>)}
            {e.generatorChanged && <li>generator: {e.generatorChanged.from} → {e.generatorChanged.to}</li>}
          </ul>
          {e.predictDelta.length > 0 && (
            <div>
              <p className="t-label mb-[4px]">Predicted</p>
              <ul className="t-data c-fg-2" style={{ overflowWrap: 'anywhere' }}>
                {e.predictDelta.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}
          <p className="t-small c-fg-3">Design is now revision v{e.version}.</p>
        </div>
      )
    case 'needs_input': {
      const s = splitList(e.text)
      return (
        <Callout tone="warn" title={s ? s.lead : 'The request needs more information'}>
          {s ? (
            <>
              <ul className="mt-[4px] flex flex-col gap-[2px]">
                {s.items.map((q, i) => (
                  <li key={i} className="flex gap-[8px]">
                    <span className="c-fg-3" aria-hidden="true">–</span>
                    <span className="t-data c-fg">{q}</span>
                  </li>
                ))}
              </ul>
              {s.tail && <p className="mt-[8px]">{s.tail}</p>}
            </>
          ) : (
            <p className="whitespace-pre-wrap">{e.text}</p>
          )}
        </Callout>
      )
    }
    case 'refused': {
      const s = splitList(e.text)
      return (
        <Callout tone="fail" role="alert" title={s ? s.lead : undefined}>
          {s ? (
            <>
              <ul className="mt-[4px] flex flex-col gap-[4px]">
                {s.items.map((r, i) => {
                  const at = r.indexOf(': ')
                  return (
                    <li key={i} className="t-small" style={{ overflowWrap: 'anywhere' }}>
                      {at > 0 ? <><span className="t-data c-fg">{r.slice(0, at)}</span> {r.slice(at + 2)}</> : r}
                    </li>
                  )
                })}
              </ul>
              {s.tail && <p className="mt-[8px]">{s.tail}</p>}
            </>
          ) : (
            <p className="whitespace-pre-wrap">{e.text}</p>
          )}
        </Callout>
      )
    }
    case 'error':
      return (
        <Callout tone="fail" role="alert">
          <p className="whitespace-pre-wrap" style={{ overflowWrap: 'anywhere' }}>{e.text}</p>
        </Callout>
      )
  }
}

/**
 * The messages lib/api.ts builds for an underdetermined request and a refusal are a lead line,
 * one `  - item` line per question or reason, then optional trailing text. Split only when the
 * message has exactly that shape; otherwise the caller prints it as it is.
 */
function splitList(text: string): { lead: string; items: string[]; tail: string } | null {
  const lines = text.split('\n')
  const isItem = (l: string) => /^ {2}- /.test(l)
  const first = lines.findIndex(isItem)
  if (first < 1) return null
  let last = first
  while (last + 1 < lines.length && isItem(lines[last + 1])) last++
  if (lines.slice(last + 1).some(isItem)) return null
  return {
    lead: lines.slice(0, first).join(' ').trim().replace(/:$/, ''),
    items: lines.slice(first, last + 1).map(l => l.replace(/^ {2}- /, '')),
    tail: lines.slice(last + 1).join(' ').trim(),
  }
}

const LIVE_EXAMPLES = [
  'Temperature sensor with DHT22, alert relay above 40°C',
  'Arduino + MAX485 RS-485 Modbus RTU master, 9600 baud',
  'LED blink with current-limiting resistor',
  'RC low-pass filter with 1kHz cutoff',
  'Voltage divider stepping 12V down to 5V',
]

// Demo mode offers exactly the prompts that have recordings (lib/demo/prompts.json).
const EXAMPLES = DEMO_MODE ? DEMO_PROMPTS : LIVE_EXAMPLES
