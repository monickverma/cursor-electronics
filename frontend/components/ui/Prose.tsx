/**
 * Prose — a tiny, safe markdown renderer for explanation text. Builds React nodes; never
 * dangerouslySetInnerHTML, so text from the API can never inject markup.
 *
 *   <Prose text={explanation} />
 *
 * Supports: `#` / `##` / `###` headings, `**bold**`, `` `code` ``, `-` / `*` bullet lists,
 * `1.` numbered lists, and paragraphs separated by blank lines (single newlines inside a
 * paragraph are kept as line breaks). Anything else is printed as text.
 * `##` headings are drawn as title-block lettering on a hairline (the explanation's sections).
 */
import { Fragment, type ReactNode } from 'react'

type Block =
  | { kind: 'h'; level: 1 | 2 | 3; text: string }
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] }

const HEADING = /^(#{1,3})\s+(.*)$/
const BULLET = /^\s*[-*]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/

export function parseBlocks(src: string): Block[] {
  const blocks: Block[] = []
  let para: string[] = []
  let list: { kind: 'ul' | 'ol'; items: string[] } | null = null

  const flushPara = () => { if (para.length) { blocks.push({ kind: 'p', lines: para }); para = [] } }
  const flushList = () => { if (list) { blocks.push(list); list = null } }

  for (const raw of src.replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) { flushPara(); flushList(); continue }

    const h = HEADING.exec(line)
    if (h) {
      flushPara(); flushList()
      blocks.push({ kind: 'h', level: h[1].length as 1 | 2 | 3, text: h[2] })
      continue
    }
    const b = BULLET.exec(line)
    const n = b ? null : NUMBERED.exec(line)
    if (b || n) {
      flushPara()
      const kind = b ? 'ul' : 'ol'
      if (!list || list.kind !== kind) { flushList(); list = { kind, items: [] } }
      list.items.push((b ?? n)![1])
      continue
    }
    // A continuation line directly under a list item belongs to it.
    if (list && /^\s{2,}\S/.test(raw)) {
      list.items[list.items.length - 1] += ' ' + line.trim()
      continue
    }
    flushList()
    para.push(line)
  }
  flushPara(); flushList()
  return blocks
}

/** Inline: **bold** and `code`. Unclosed markers are printed as they are. */
export function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = []
  const re = /(\*\*([^*]+)\*\*|`([^`]+)`)/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    if (m[2] !== undefined) out.push(<strong key={k++}>{m[2]}</strong>)
    else out.push(<code key={k++}>{m[3]}</code>)
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function Prose({ text, className = '' }: { text: string; className?: string }) {
  const blocks = parseBlocks(text)
  return (
    <div className={`prose ${className}`}>
      {blocks.map((b, i) => {
        if (b.kind === 'h') {
          const H = (`h${b.level}` as 'h1' | 'h2' | 'h3')
          return <H key={i}>{renderInline(b.text)}</H>
        }
        if (b.kind === 'ul' || b.kind === 'ol') {
          const L = b.kind
          return <L key={i}>{b.items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}</L>
        }
        return (
          <p key={i}>
            {b.lines.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {renderInline(l)}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
