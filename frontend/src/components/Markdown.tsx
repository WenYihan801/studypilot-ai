import { Fragment, type ReactNode } from 'react'

/**
 * Tiny, safe markdown renderer for AI answers. Builds React elements (never innerHTML),
 * so model output cannot inject scripts. Supports paragraphs, -/1. lists, ### headings,
 * **bold**, `code` and [S1] citation chips.
 */
function inline(text: string, onCite?: (label: string) => void): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[S\d+\])/g)
  return parts.map((p, i) => {
    if (/^\*\*[^*]+\*\*$/.test(p)) return <strong key={i}>{p.slice(2, -2)}</strong>
    if (/^`[^`]+`$/.test(p)) return <code key={i}>{p.slice(1, -1)}</code>
    const cite = p.match(/^\[(S\d+)\]$/)
    if (cite) {
      return (
        <button key={i} type="button" onClick={() => onCite?.(cite[1])}
          className="mx-0.5 inline-flex h-5 items-center rounded bg-brand-50 px-1.5 align-baseline text-[11px] font-semibold text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100"
          aria-label={`Show source ${cite[1]}`}>
          {cite[1]}
        </button>
      )
    }
    return <Fragment key={i}>{p}</Fragment>
  })
}

export function Markdown({ text, onCite }: { text: string; onCite?: (label: string) => void }) {
  const blocks: ReactNode[] = []
  const lines = text.split('\n')
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    const h = line.match(/^#{1,4}\s+(.*)/)
    if (h) { blocks.push(<h4 key={i}>{inline(h[1], onCite)}</h4>); i++; continue }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(<li key={i}>{inline(lines[i].replace(/^\s*[-*]\s+/, ''), onCite)}</li>); i++
      }
      blocks.push(<ul key={`ul${i}`}>{items}</ul>); continue
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: ReactNode[] = []
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(<li key={i}>{inline(lines[i].replace(/^\s*\d+[.)]\s+/, ''), onCite)}</li>); i++
      }
      blocks.push(<ol key={`ol${i}`}>{items}</ol>); continue
    }
    const para: string[] = []
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\s*[-*]\s|\s*\d+[.)]\s)/.test(lines[i])) { para.push(lines[i]); i++ }
    blocks.push(<p key={`p${i}`}>{inline(para.join(' '), onCite)}</p>)
  }
  return <div className="prose-answer text-sm text-slate-800">{blocks}</div>
}
