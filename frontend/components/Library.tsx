'use client'

/**
 * The library: every design this account has made, filed by project, down the
 * left edge. Opening one brings back the design and the conversation that led
 * to it (app/page.tsx does the loading; this lists and files).
 *
 * It is read from the backend each time — nothing here is the record. A design
 * filed under a project is the same design: filing never touches its
 * requirement, version or claims.
 */

import { useEffect, useMemo, useState, FormEvent } from 'react'
import {
  createProject, fileDesign, listDesigns, listProjects,
  type DesignSummary, type Project,
} from '@/lib/api'

interface Props {
  token: string
  email?: string
  activeId?: string
  /** Bumped by the page whenever a design is made or revised, to read the list again. */
  refreshKey: number
  open: boolean
  onToggle: () => void
  onOpenDesign: (circuitId: string) => void
  onNewDesign: () => void
  onSignOut: () => void
}

const UNFILED = '__unfiled__'

function when(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export default function Library({
  token, email, activeId, refreshKey, open, onToggle, onOpenDesign, onNewDesign, onSignOut,
}: Props) {
  const [designs, setDesigns] = useState<DesignSummary[] | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [closed, setClosed] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!token) return
    let stale = false
    Promise.all([listDesigns(token), listProjects(token)])
      .then(([d, p]) => {
        if (stale) return
        setDesigns(d)
        setProjects(p)
        setError('')
      })
      .catch(e => { if (!stale) setError(e instanceof Error ? e.message : 'The library could not be read.') })
    return () => { stale = true }
  }, [token, refreshKey])

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase()
    const shown = (designs ?? []).filter(d => !q || d.intent.toLowerCase().includes(q))
    const known = new Set(projects.map(p => p.id))
    return [
      ...projects.map(p => ({ id: p.id, name: p.name, items: shown.filter(d => d.project_id === p.id) })),
      { id: UNFILED, name: 'Not filed', items: shown.filter(d => !d.project_id || !known.has(d.project_id)) },
    ]
  }, [designs, projects, query])

  async function addProject(e: FormEvent) {
    e.preventDefault()
    const wanted = name.trim()
    if (!wanted) return
    try {
      const made = await createProject(wanted, token)
      setProjects(p => [...p, made])
      setName('')
      setNaming(false)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The project could not be made.')
    }
  }

  async function move(circuitId: string, projectId: string) {
    const target = projectId === UNFILED ? null : projectId
    try {
      await fileDesign(circuitId, target, token)
      setDesigns(ds => (ds ?? []).map(d => (d.circuit_id === circuitId ? { ...d, project_id: target } : d)))
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The design could not be moved.')
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={onToggle} aria-label="Open the library" aria-expanded={false}
              className="fixed left-0 top-[52px] z-30 min-h-[44px] px-3 bg-paper text-ink border-[1.5px] border-l-0 border-ink font-pixel text-xl">
        LIBRARY
      </button>
    )
  }

  return (
    <aside aria-label="Library" data-testid="library"
           className="fixed left-0 top-0 bottom-0 z-30 w-[288px] max-w-[86vw] flex flex-col bg-ink text-paper border-r-[1.5px] border-paper/30">
      <div className="flex items-center justify-between gap-2 pl-3.5 pr-1 min-h-[44px] bg-paper text-ink">
        <span className="font-pixel text-2xl tracking-wider">CIRCUIT OS</span>
        <button type="button" onClick={onToggle} aria-label="Close the library" aria-expanded={true}
                className="w-11 h-11 font-pixel text-2xl hover:bg-ink hover:text-paper">
          ×
        </button>
      </div>

      <div className="flex flex-col gap-2 p-3 border-b border-paper/20">
        <button type="button" onClick={onNewDesign}
                className="min-h-[44px] px-3 bg-paper text-ink font-sans text-[15px] font-semibold text-left hover:bg-transparent hover:text-paper border-[1.5px] border-paper">
          + New design
        </button>
        <input
          type="search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search your designs"
          aria-label="Search your designs"
          className="min-h-[40px] px-3 bg-transparent text-paper border-[1.5px] border-paper/40 font-mono text-xs placeholder:text-paper/60 focus:border-paper outline-none"
        />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto scroll-dark">
        {error && <p role="alert" className="m-3 p-2 border border-[#ff9d94] text-[#ffb4ac] text-xs">{error}</p>}
        {designs === null && !error && <p className="p-3 text-xs text-paper/70">Reading your designs…</p>}
        {designs !== null && designs.length === 0 && (
          <p className="p-3 text-xs text-paper/70 leading-relaxed">
            Nothing saved yet. Every design you build is kept here, with the conversation that led to it.
          </p>
        )}

        {designs !== null && groups.map(g => {
          if (g.id === UNFILED && g.items.length === 0 && projects.length > 0) return null
          if (g.id === UNFILED && designs.length === 0) return null
          const isClosed = !!closed[g.id]
          return (
            <section key={g.id} aria-label={g.name}>
              <button type="button" aria-expanded={!isClosed}
                      onClick={() => setClosed(c => ({ ...c, [g.id]: !c[g.id] }))}
                      className="w-full flex items-center justify-between gap-2 min-h-[36px] px-3 font-pixel text-lg text-left text-paper/90 hover:bg-paper/10">
                <span className="truncate">{isClosed ? '▸' : '▾'} {g.name}</span>
                <span className="font-mono text-[11px] text-paper/60">{g.items.length}</span>
              </button>
              {!isClosed && (
                <ul className="flex flex-col">
                  {g.items.length === 0 && (
                    <li className="px-3 pb-2 text-[11px] text-paper/50">
                      {query ? 'No match here.' : 'Empty. Open a design and move it here.'}
                    </li>
                  )}
                  {g.items.map(d => {
                    const active = d.circuit_id === activeId
                    return (
                      <li key={d.circuit_id}>
                        <button type="button" onClick={() => onOpenDesign(d.circuit_id)}
                                aria-current={active ? 'true' : undefined}
                                data-design={d.circuit_id}
                                className={`w-full px-3 py-2 text-left border-l-[3px] ${
                                  active ? 'bg-paper text-ink border-paper' : 'border-transparent hover:bg-paper/10'}`}>
                          <span className="block font-sans text-[13px] leading-snug line-clamp-2">{d.intent}</span>
                          <span className={`block mt-0.5 font-mono text-[10.5px] ${active ? 'text-ink/70' : 'text-paper/55'}`}>
                            v{d.version}{d.target_mcu ? ` · ${d.target_mcu}` : ''} · {when(d.updated_at ?? d.created_at)}
                          </span>
                        </button>
                        {active && (
                          <label className="flex items-center gap-2 px-3 py-1.5 bg-paper text-ink font-mono text-[11px]">
                            File under
                            <select
                              value={d.project_id && projects.some(p => p.id === d.project_id) ? d.project_id : UNFILED}
                              onChange={e => move(d.circuit_id, e.target.value)}
                              className="flex-1 min-w-0 min-h-[28px] bg-paper text-ink border border-ink font-mono text-[11px]"
                            >
                              <option value={UNFILED}>Not filed</option>
                              {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                            </select>
                          </label>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>
          )
        })}
      </div>

      <div className="p-3 border-t border-paper/20 flex flex-col gap-2">
        {naming ? (
          <form onSubmit={addProject} className="flex gap-1.5">
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={80}
              placeholder="Project name"
              aria-label="Project name"
              className="flex-1 min-w-0 min-h-[40px] px-2 bg-transparent text-paper border-[1.5px] border-paper font-mono text-xs outline-none"
            />
            <button type="submit" className="min-h-[40px] px-3 bg-paper text-ink font-sans text-sm font-semibold">Add</button>
          </form>
        ) : (
          <button type="button" onClick={() => setNaming(true)}
                  className="min-h-[40px] px-3 text-left font-mono text-xs border-[1.5px] border-paper/40 hover:border-paper">
            + New project
          </button>
        )}
        <div className="flex items-center justify-between gap-2 font-mono text-[11px] text-paper/70">
          <span className="truncate" title={email}>{email ?? 'Signed in'}</span>
          <button type="button" onClick={onSignOut} className="min-h-[32px] px-2 underline underline-offset-4 hover:text-paper">
            Sign out
          </button>
        </div>
      </div>
    </aside>
  )
}
