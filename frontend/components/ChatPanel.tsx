'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { generateDesign, patchDesign, login, register, GenerateResponse, PatchResponse } from '@/lib/api'

interface Message {
  role: 'user' | 'assistant' | 'error'
  text: string
  timestamp: Date
}

interface Props {
  onResult: (res: GenerateResponse | PatchResponse) => void
  token: string
  onTokenChange: (t: string) => void
  currentCircuitId?: string
}

type AuthMode = 'login' | 'register'

export default function ChatPanel({ onResult, token, onTokenChange, currentCircuitId }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('test@circuitos.dev')
  const [password, setPassword] = useState('TestPass123!')
  const [authError, setAuthError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text, timestamp: new Date() }])
    setLoading(true)
    try {
      let res: GenerateResponse | PatchResponse
      if (currentCircuitId && messages.length > 0) {
        res = await patchDesign(currentCircuitId, text, token)
        const p = res as PatchResponse
        const summary = p.changes.length > 0
          ? `Applied ${p.changes.length} change(s). Design is now v${p.version}.`
          : p.note_to_user || 'No changes applied.'
        setMessages(prev => [...prev, { role: 'assistant', text: summary, timestamp: new Date() }])
      } else {
        res = await generateDesign(text, token)
        const g = res as GenerateResponse
        const summary = `Generated ${g.application_class}${g.target_mcu ? ` on ${g.target_mcu}` : ''} — v${g.version}.\n\n${g.explanation.slice(0, 360)}…`
        setMessages(prev => [...prev, { role: 'assistant', text: summary, timestamp: new Date() }])
      }
      onResult(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setMessages(prev => [...prev, { role: 'error', text: msg, timestamp: new Date() }])
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  /* ── Auth screen ───────────────────────────────────────────── */
  if (!token) {
    return (
      <div
        className="flex-1 flex items-center justify-center"
        style={{ padding: '2rem 1.5rem', background: 'var(--lumen)' }}
      >
        <div style={{ width: '100%', maxWidth: 320 }}>
          <h2
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'var(--h4)',
              color: 'var(--vast)',
              fontStyle: 'italic',
              textAlign: 'center',
              marginBottom: '1.75rem',
            }}
          >
            {authMode === 'login' ? 'Welcome back' : 'Get started'}
          </h2>

          <form onSubmit={handleAuth} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="input-light"
              style={{ padding: '10px 14px', width: '100%' }}
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="input-light"
              style={{ padding: '10px 14px', width: '100%' }}
            />
            {authError && (
              <p style={{ fontSize: 'var(--body-xs)', color: '#dc2626' }}>{authError}</p>
            )}
            <button
              type="submit"
              className="btn-amber"
              style={{ padding: '11px 0', width: '100%', marginTop: 4 }}
            >
              {authMode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <button
            onClick={() => setAuthMode(m => m === 'login' ? 'register' : 'login')}
            style={{
              display: 'block',
              width: '100%',
              marginTop: 12,
              textAlign: 'center',
              fontSize: 'var(--body-xs)',
              color: 'var(--text-muted-light)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = 'var(--vast)'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = 'var(--text-muted-light)'}
          >
            {authMode === 'login' ? 'No account? Register →' : '← Back to sign in'}
          </button>
        </div>
      </div>
    )
  }

  /* ── Chat screen ───────────────────────────────────────────── */
  return (
    <div className="flex-1 flex flex-col min-h-0" style={{ background: 'var(--lumen)' }}>

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto scroll-light"
        style={{ padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        {messages.length === 0 && (
          <div style={{ paddingTop: '0.5rem' }}>
            <p style={{ fontSize: 'var(--body-xs)', color: 'var(--text-muted-light)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}>
              Try an example
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => setInput(ex)}
                  style={{
                    textAlign: 'left',
                    fontSize: 'var(--body-xs)',
                    color: 'var(--text-muted-light)',
                    background: 'white',
                    border: '1px solid var(--border-light)',
                    borderRadius: 'var(--r-sm)',
                    padding: '8px 12px',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s, color 0.15s',
                    lineHeight: 1.5,
                  }}
                  onMouseEnter={e => {
                    const el = e.currentTarget as HTMLElement
                    el.style.borderColor = 'var(--vast)'
                    el.style.color = 'var(--vast)'
                  }}
                  onMouseLeave={e => {
                    const el = e.currentTarget as HTMLElement
                    el.style.borderColor = 'var(--border-light)'
                    el.style.color = 'var(--text-muted-light)'
                  }}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          borderTop: '1px solid var(--border-light)',
          padding: '0.875rem 1.25rem',
          background: 'var(--lumen)',
        }}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={currentCircuitId ? 'Request a change…' : 'Describe your circuit…'}
            rows={1}
            disabled={loading}
            className="input-light"
            style={{
              flex: 1,
              padding: '9px 13px',
              resize: 'none',
              lineHeight: 1.5,
            }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="btn-amber"
            style={{ padding: '9px 16px', flexShrink: 0 }}
          >
            {loading ? '…' : '→'}
          </button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted-light)', marginTop: 6 }}>
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  )
}

/* ── Message bubble ────────────────────────────────────────────── */
function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'

  if (isUser) {
    return (
      <div className="fade-up" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <div
          style={{
            maxWidth: '82%',
            background: 'var(--vast)',
            color: 'var(--lumen)',
            borderRadius: 'var(--r-md) var(--r-md) 4px var(--r-md)',
            padding: '9px 14px',
            fontSize: 'var(--body-sm)',
            lineHeight: 1.6,
          }}
        >
          {msg.text}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="fade-up" style={{ display: 'flex', justifyContent: 'flex-start' }}>
        <div
          style={{
            maxWidth: '88%',
            background: '#fff0f0',
            border: '1px solid #fecaca',
            borderRadius: 'var(--r-md) var(--r-md) var(--r-md) 4px',
            padding: '9px 14px',
            fontSize: 'var(--body-xs)',
            color: '#dc2626',
            lineHeight: 1.6,
          }}
        >
          {msg.text}
        </div>
      </div>
    )
  }

  return (
    <div className="fade-up" style={{ display: 'flex', justifyContent: 'flex-start' }}>
      <div
        style={{
          maxWidth: '88%',
          background: 'white',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--r-md) var(--r-md) var(--r-md) 4px',
          padding: '10px 14px',
          fontSize: 'var(--body-sm)',
          color: 'var(--vast)',
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
        }}
      >
        {msg.text}
      </div>
    </div>
  )
}

/* ── Typing indicator ──────────────────────────────────────────── */
function TypingIndicator() {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
      <div
        style={{
          background: 'white',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--r-md) var(--r-md) var(--r-md) 4px',
          padding: '12px 16px',
          display: 'flex',
          gap: 4,
          alignItems: 'center',
        }}
      >
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className={`dot-${i + 1}`}
            style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'var(--text-muted-light)',
            }}
          />
        ))}
      </div>
    </div>
  )
}

const EXAMPLES = [
  'Temperature sensor with DHT22, alert relay above 40°C',
  'Arduino + MAX485 RS-485 Modbus RTU master, 9600 baud',
  'LED blink with current-limiting resistor',
  'RC low-pass filter with 1kHz cutoff',
  'Voltage divider stepping 12V down to 5V',
]
