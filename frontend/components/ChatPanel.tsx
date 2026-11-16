'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { generateDesign, patchDesign, login, register, UnderdeterminedError, GenerateResponse, PatchResponse } from '@/lib/api'
import { DEMO_MODE, DEMO_PROMPTS } from '@/lib/demo'
import FloatWindow from '@/components/FloatWindow'
import Markdown, { excerpt } from '@/components/Markdown'

export interface Message {
  role: 'user' | 'assistant' | 'error'
  text: string
  timestamp: Date
}

interface Props {
  onResult: (res: GenerateResponse | PatchResponse) => void
  token: string
  onTokenChange: (t: string) => void
  currentCircuitId?: string
  /** Which conversation this is. When it changes, the log is replaced by `initialMessages`. */
  threadKey?: string
  /** The conversation so far, when a saved design is opened from the library. */
  initialMessages?: Message[]
  /** A request to place in the prompt bar, ready to send (a template chosen on the front page). */
  seedPrompt?: string
}

type AuthMode = 'login' | 'register'

/**
 * The prompt bar under the headline, and the conversation that hangs below it.
 * Before sign-in it is the sign-in window instead.
 */
export default function ChatPanel({ onResult, token, onTokenChange, currentCircuitId, threadKey, initialMessages, seedPrompt }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  // The request the system asked about. Held until it is answered, so the reply is added to it.
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('test@circuitos.dev')
  const [password, setPassword] = useState('TestPass123!')
  const [authError, setAuthError] = useState('')
  const logRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // A different conversation (a design opened from the library, or a new one):
  // start from its messages, and drop anything half-asked in the old one.
  const startWith = useRef(initialMessages)
  startWith.current = initialMessages
  useEffect(() => {
    if (threadKey === undefined) return
    setMessages(startWith.current ?? [])
    setPendingPrompt(null)
    setInput('')
  }, [threadKey])

  // A template picked on the front page: written into the bar once the person is
  // signed in, and left for them to send.
  useEffect(() => {
    if (seedPrompt && token) setInput(seedPrompt)
  }, [seedPrompt, token])

  // Bring the latest exchange to the top of the log, so a reply is read from its
  // first line. Only the log scrolls; the page itself does not jump.
  useEffect(() => {
    const log = logRef.current
    if (!log) return
    const asked = Array.from(log.querySelectorAll<HTMLElement>('[data-role="user"]')).pop()
    log.scrollTop = asked ? asked.offsetTop : log.scrollHeight
  }, [messages, loading])

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
    setMessages(prev => [...prev, { role: 'user', text, timestamp: new Date() }])
    setLoading(true)
    try {
      let res: GenerateResponse | PatchResponse
      if (currentCircuitId && messages.length > 0 && !DEMO_MODE) {
        res = await patchDesign(currentCircuitId, text, token)
        const p = res as PatchResponse
        const delta = p.predict_delta?.length ? `\n\nPredicted: ${p.predict_delta.join('; ')}` : ''
        const summary = p.changes.length > 0
          ? `Requirement changed — ${p.changes.join('; ')}. Design is now v${p.version}.${delta}`
          : p.note_to_user || 'No changes applied.'
        setMessages(prev => [...prev, { role: 'assistant', text: summary, timestamp: new Date() }])
      } else {
        const prompt = pendingPrompt ? `${pendingPrompt}. ${text}` : text
        res = await generateDesign(prompt, token)
        setPendingPrompt(null)
        const g = res as GenerateResponse
        // The opening of the explanation, cut between paragraphs; the whole of it is under Validation.
        const opening = g.explanation ? excerpt(g.explanation, 360) : null
        const summary = `Generated ${g.application_class}${g.target_mcu ? ` on ${g.target_mcu}` : ''} — v${g.version}.\n\n${
          opening
            ? `${opening.text}${opening.cut ? '\n\nThe rest is under Validation.' : ''}`
            : 'The explanation is being written; it appears under Validation in about a minute.'}`
        setMessages(prev => [...prev, { role: 'assistant', text: summary, timestamp: new Date() }])
      }
      onResult(res)
    } catch (err: unknown) {
      if (err instanceof UnderdeterminedError) setPendingPrompt(pendingPrompt ? `${pendingPrompt}. ${text}` : text)
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setMessages(prev => [...prev, { role: 'error', text: msg, timestamp: new Date() }])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  /* ── Sign-in window ────────────────────────────────────────── */
  if (!token) {
    return (
      <FloatWindow id="auth" title={authMode === 'login' ? 'Welcome back' : 'Get started'} className="w-full max-w-[380px] text-left">
        <form onSubmit={handleAuth} className="flex flex-col gap-3 p-5">
          <input
            type="email"
            placeholder="Email address"
            aria-label="Email address"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="flow-field"
          />
          <input
            type="password"
            placeholder="Password"
            aria-label="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="flow-field"
          />
          {authError && <p className="text-sm text-bad">{authError}</p>}
          <button type="submit" className="flow-btn !bg-ink !text-paper mt-1">
            {authMode === 'login' ? 'Sign in' : 'Create account'}
          </button>
          <button
            type="button"
            onClick={() => setAuthMode(m => m === 'login' ? 'register' : 'login')}
            className="min-h-[44px] font-mono text-xs text-muted underline underline-offset-4 hover:text-cream"
          >
            {authMode === 'login' ? 'No account? Register →' : '← Back to sign in'}
          </button>
        </form>
      </FloatWindow>
    )
  }

  /* ── Prompt bar and conversation ───────────────────────────── */
  return (
    <div className="w-full max-w-[760px] flex flex-col gap-3 text-left">
      <div className="flex flex-wrap items-stretch border-[1.5px] border-ink bg-paper shadow-[5px_5px_0_rgba(254,254,254,0.3)]">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder={DEMO_MODE ? 'Pick a recorded example…' : currentCircuitId ? 'Request a change…' : 'Describe your circuit…'}
          rows={1}
          disabled={loading}
          className="flow-field !border-0 flex-[999_1_240px] min-w-0 resize-none leading-normal"
        />
        <button
          type="button"
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          className="flex-[1_1_auto] min-h-[44px] px-6 bg-ink text-paper font-sans text-base font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? '…' : currentCircuitId ? 'Rebuild' : 'Build'}
        </button>
      </div>

      {/* The key hint is for a first visit; with a design open it only pushes the windows down. */}
      {(DEMO_MODE || !currentCircuitId) && (
        <p className="text-xs text-center text-paper">
          {DEMO_MODE
            ? 'Demo mode: only the recorded examples can be opened.'
            : 'Enter to send · Shift+Enter for newline'}
        </p>
      )}

      {(messages.length === 0 || DEMO_MODE) && (
        <div className="flex flex-col gap-2">
          {messages.length === 0 && (
            <p className="font-pixel text-lg leading-none text-center text-paper">
              {DEMO_MODE ? 'Recorded examples — click to open' : 'Try an example'}
            </p>
          )}
          <div className="flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((ex, i) => (
              <button
                key={i}
                type="button"
                // In demo mode an example is a recording: open it at once.
                onClick={() => (DEMO_MODE ? handleSend(ex) : setInput(ex))}
                disabled={loading}
                title={ex}
                className="min-h-[44px] max-w-full px-3 py-2 bg-paper text-ink border-[1.5px] border-ink font-mono text-xs text-left hover:bg-ink hover:text-paper hover:border-paper disabled:opacity-50"
              >
                {messages.length > 0 && ex.length > 42 ? `${ex.slice(0, 40)}…` : ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {(messages.length > 0 || loading) && (
        <div
          ref={logRef}
          role="log"
          aria-label="Conversation"
          className={`paper relative overflow-y-auto border-[1.5px] border-ink shadow-[5px_5px_0_rgba(254,254,254,0.3)] divide-y divide-border/20 ${
            // With a design on the desktop the log gives way to it; it still scrolls.
            currentCircuitId ? 'max-h-[128px]' : 'max-h-[260px]'}`}
        >
          {messages.map((msg, i) => (
            <MessageRow key={i} msg={msg} />
          ))}
          {loading && (
            <div className="flex items-center gap-3 px-4 py-3">
              <span className="font-pixel text-lg leading-none w-24 shrink-0">CIRCUIT OS</span>
              <span className="flex items-center gap-1" aria-label="Working">
                {[0, 1, 2].map(i => (
                  <span key={i} className={`dot-${i + 1} inline-block w-1.5 h-1.5 bg-cream`} />
                ))}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── One line of the conversation ──────────────────────────────── */
function MessageRow({ msg }: { msg: Message }) {
  const who = msg.role === 'user' ? 'YOU' : msg.role === 'error' ? 'NOT BUILT' : 'CIRCUIT OS'
  return (
    <div data-role={msg.role} className="fade-up flex flex-wrap gap-x-3 gap-y-1 px-4 py-3">
      <span className={`font-pixel text-lg leading-none w-24 shrink-0 pt-0.5 ${msg.role === 'error' ? 'text-bad' : 'text-cream'}`}>
        {who}
      </span>
      {msg.role === 'assistant' ? (
        <Markdown text={msg.text} className="flex-[1_1_240px] min-w-0" />
      ) : (
        <p className={`flex-[1_1_240px] min-w-0 text-sm leading-relaxed whitespace-pre-wrap ${
          msg.role === 'error' ? 'text-bad' : 'font-medium text-cream'
        }`}>
          {msg.text}
        </p>
      )}
    </div>
  )
}

// Each of these states every value its generator needs, so it builds as written
// instead of coming back with questions. Checked against the live backend 2026-11-15.
const LIVE_EXAMPLES = [
  'Room monitor: an Uno reads a DHT22 on a 2 m cable, sounds a 30 mA buzzer above 30 °C, and lights a status LED at 10 mA',
  'Arduino Uno + MAX485 RS-485 Modbus RTU master at 9600 baud on a 5 V supply',
  'Arduino Uno driving a status LED at 10 mA from a 5 V supply',
  'RC low-pass filter with a 1 kHz cutoff on a 5 V supply',
  'Voltage divider stepping 5 V down to 3.3 V',
]

// Demo mode offers exactly the prompts that have recordings (lib/demo/prompts.json).
const EXAMPLES = DEMO_MODE ? DEMO_PROMPTS : LIVE_EXAMPLES
