/**
 * The explanation arrives as Markdown text. This draws the part of Markdown it
 * actually uses — headings, paragraphs, lists, **bold**, *italic*, `code`, fenced
 * code — as React elements.
 *
 * It never builds HTML from the text: anything it does not recognise is shown as
 * the characters it is. The explanation can quote the user's own prompt, so
 * treating it as markup to inject would be an injection path.
 */

import { Fragment, ReactNode } from 'react'

type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'para'; text: string }
  | { kind: 'list'; ordered: boolean; items: string[] }
  | { kind: 'code'; text: string }

const HEADING = /^(#{1,6})\s+(.*)$/
const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/
const FENCE = /^\s*```/

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  let para: string[] = []
  const flush = () => {
    if (para.length) blocks.push({ kind: 'para', text: para.join(' ') })
    para = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (FENCE.test(line)) {
      flush()
      const code: string[] = []
      i += 1
      while (i < lines.length && !FENCE.test(lines[i])) {
        code.push(lines[i])
        i += 1
      }
      blocks.push({ kind: 'code', text: code.join('\n') })
      continue
    }
    if (!line.trim()) {
      flush()
      continue
    }
    const heading = HEADING.exec(line)
    if (heading) {
      flush()
      blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2].trim() })
      continue
    }
    const bullet = BULLET.exec(line)
    const numbered = bullet ? null : NUMBERED.exec(line)
    if (bullet || numbered) {
      flush()
      const ordered = !bullet
      const item = (bullet ?? numbered)![1]
      const last = blocks[blocks.length - 1]
      if (last && last.kind === 'list' && last.ordered === ordered) last.items.push(item)
      else blocks.push({ kind: 'list', ordered, items: [item] })
      continue
    }
    para.push(line.trim())
  }
  flush()
  return blocks
}

// **bold**, *italic*, `code`. Underscores are left alone: net and field names are full of them.
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\s][^*\n]*\*)/g

function inline(text: string): ReactNode {
  const parts = text.split(INLINE)
  return parts.map((part, i) => {
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-cream">{part.slice(2, -2)}</strong>
    }
    if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="font-mono text-[0.92em] px-1 bg-surface-2">{part.slice(1, -1)}</code>
    }
    if (part.length > 2 && part.startsWith('*') && part.endsWith('*')) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }
    return <Fragment key={i}>{part}</Fragment>
  })
}

/**
 * The opening of a Markdown text, cut at a block boundary so no mark-up is left
 * half open. Returns the text and whether anything was left out.
 */
export function excerpt(text: string, maxChars: number): { text: string; cut: boolean } {
  const chunks = text.replace(/\r\n?/g, '\n').split(/\n{2,}/)
  const kept: string[] = []
  let used = 0
  for (const chunk of chunks) {
    if (kept.length > 0 && used + chunk.length > maxChars) break
    kept.push(chunk)
    used += chunk.length
  }
  return { text: kept.join('\n\n'), cut: kept.length < chunks.length }
}

export default function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = parseBlocks(text)
  return (
    <div className={`flex flex-col gap-3 text-sm leading-relaxed text-cream-dim ${className ?? ''}`}>
      {blocks.map((b, i) => {
        if (b.kind === 'heading') {
          // The window already has its title; the text's own headings sit below it.
          return b.level <= 2
            ? <h4 key={i} className="mt-2 first:mt-0 text-base font-semibold text-cream">{inline(b.text)}</h4>
            : <h5 key={i} className="mt-1 first:mt-0 text-sm font-semibold text-cream">{inline(b.text)}</h5>
        }
        if (b.kind === 'list') {
          const List = b.ordered ? 'ol' : 'ul'
          return (
            <List key={i} className={`pl-5 flex flex-col gap-1 ${b.ordered ? 'list-decimal' : 'list-disc'}`}>
              {b.items.map((item, j) => <li key={j}>{inline(item)}</li>)}
            </List>
          )
        }
        if (b.kind === 'code') {
          return (
            <pre key={i} className="p-3 font-mono text-xs leading-relaxed bg-surface-2 overflow-x-auto">{b.text}</pre>
          )
        }
        return <p key={i} className="max-w-[72ch]">{inline(b.text)}</p>
      })}
    </div>
  )
}
