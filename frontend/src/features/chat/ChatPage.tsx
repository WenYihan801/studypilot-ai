import { AlertTriangle, FileText, MessageSquarePlus, Send, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Markdown } from '@/components/Markdown'
import { Alert, Button, Card, EmptyState, ErrorState, Spinner, Textarea } from '@/components/ui'
import { useWorkspaceContext } from '@/features/workspaces/WorkspaceLayout'
import { useAsk, useConversation, useConversations, useDeleteConversation, useDocuments } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { cn, relativeTime } from '@/lib/utils'
import type { Citation, Message } from '@/types/api'

export function SourceCard({ c, highlighted }: { c: Citation; highlighted?: boolean }) {
  return (
    <div id={`src-${c.chunk_id}`} className={cn('rounded-lg border bg-white p-3 text-xs transition-shadow', highlighted ? 'border-brand-500 ring-2 ring-brand-100' : 'border-slate-200')}>
      <div className="mb-1 flex items-center gap-1.5 font-medium text-slate-800">
        <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[11px] font-semibold text-brand-700">{c.label}</span>
        <FileText className="size-3.5 shrink-0 text-slate-400" />
        <span className="truncate" title={c.filename}>{c.filename}</span>
      </div>
      <div className="mb-1.5 text-slate-500">
        {c.page_number ? `Page ${c.page_number}` : c.section_title ? `Section: ${c.section_title}` : 'Full text'}
        {c.score !== null && <span title="Cosine similarity between your question and this passage"> · {Math.round(c.score * 100)}% match</span>}
      </div>
      <p className="line-clamp-4 text-slate-600">“{c.quote_text}”</p>
    </div>
  )
}

function AssistantMessage({ m }: { m: Message }) {
  const [active, setActive] = useState<string | null>(null)
  const onCite = (label: string) => {
    const c = m.citations.find((x) => x.label === label)
    if (!c) return
    setActive(c.chunk_id)
    document.getElementById(`src-${c.chunk_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
  return (
    <div className="max-w-3xl">
      <Card className="p-4">
        {m.insufficient_evidence && (
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-amber-700"><AlertTriangle className="size-3.5" /> Not enough evidence in your materials</div>
        )}
        <Markdown text={m.content} onCite={onCite} />
      </Card>
      {m.citations.length > 0 && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {m.citations.map((c) => <SourceCard key={c.chunk_id} c={c} highlighted={active === c.chunk_id} />)}
        </div>
      )}
    </div>
  )
}

const SUGGESTIONS = ['Summarise the main points of these materials.', 'Explain the hardest concept in simpler language.', 'Give me a practical example of a key idea.']

export function ChatPage() {
  const { workspace } = useWorkspaceContext()
  const [params, setParams] = useSearchParams()
  const conversationId = params.get('c')
  const conversations = useConversations(workspace.id)
  const conversation = useConversation(conversationId)
  const docs = useDocuments(workspace.id)
  const ask = useAsk(workspace.id)
  const del = useDeleteConversation(workspace.id)
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const readyCount = docs.data?.filter((d) => d.status === 'READY').length ?? 0

  const messages = conversation.data?.messages ?? []
  useEffect(() => { bottom.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages.length, pending])

  async function send(text: string) {
    const q = text.trim()
    if (!q || ask.isPending) return
    setPending(q)
    setQuestion('')
    try {
      const res = await ask.mutateAsync({ question: q, conversation_id: conversationId })
      if (res.conversation_id !== conversationId) setParams({ c: res.conversation_id })
    } catch {
      setQuestion(q)
    } finally {
      setPending(null)
    }
  }
  const onSubmit = (e: FormEvent) => { e.preventDefault(); send(question) }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(question) } }

  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
      <aside className="space-y-2">
        <Button variant="secondary" className="w-full" onClick={() => setParams({})}><MessageSquarePlus className="size-4" /> New chat</Button>
        <div className="max-h-[60vh] space-y-1 overflow-y-auto">
          {conversations.data?.map((c) => (
            <div key={c.id} className={cn('group flex items-center rounded-lg text-sm', c.id === conversationId ? 'bg-brand-50 text-brand-700' : 'hover:bg-slate-100')}>
              <button className="min-w-0 flex-1 truncate px-3 py-2 text-left" onClick={() => setParams({ c: c.id })} title={c.title}>
                {c.title}<span className="block text-xs text-slate-500">{relativeTime(c.updated_at)}</span>
              </button>
              <button aria-label="Delete conversation" className="mr-1 rounded p-1 text-slate-400 opacity-0 hover:text-red-600 group-hover:opacity-100 focus:opacity-100"
                onClick={async () => { await del.mutateAsync(c.id); if (c.id === conversationId) setParams({}) }}><Trash2 className="size-3.5" /></button>
            </div>
          ))}
        </div>
      </aside>

      <section className="flex min-h-[60vh] flex-col">
        <div className="flex-1 space-y-5">
          {readyCount === 0 && !docs.isLoading && (
            <Alert tone="warning">No processed documents in this workspace yet. <Link className="underline" to={`/app/workspaces/${workspace.id}`}>Upload materials</Link> so answers can be grounded in them.</Alert>
          )}
          {conversation.isLoading ? <Spinner /> : conversation.error ? <ErrorState message={errorMessage(conversation.error)} /> : messages.length === 0 && !pending ? (
            <EmptyState title="Ask about your course materials" description={`Answers are grounded in the ${readyCount} ready document(s) in “${workspace.name}”, with page-level sources.`}
              action={<div className="flex flex-wrap justify-center gap-2">{SUGGESTIONS.map((s) => <Button key={s} size="sm" variant="secondary" onClick={() => send(s)}>{s}</Button>)}</div>} />
          ) : (
            messages.map((m) => m.role === 'user'
              ? <div key={m.id} className="flex justify-end"><div className="max-w-2xl rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-sm text-white whitespace-pre-wrap">{m.content}</div></div>
              : <AssistantMessage key={m.id} m={m} />)
          )}
          {pending && (
            <>
              <div className="flex justify-end"><div className="max-w-2xl rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-sm text-white whitespace-pre-wrap">{pending}</div></div>
              <Card className="max-w-3xl p-4"><Spinner label="Searching your materials and writing an answer…" /></Card>
            </>
          )}
          {ask.error && <Alert tone="error">{errorMessage(ask.error)}</Alert>}
          <div ref={bottom} />
        </div>

        <form onSubmit={onSubmit} className="sticky bottom-0 mt-6 bg-slate-50 pb-2 pt-2">
          <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100">
            <Textarea aria-label="Your question" rows={2} maxLength={2000} value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKey}
              placeholder="Ask a question about this course… (Enter to send, Shift+Enter for a new line)" className="resize-none border-0 shadow-none focus:ring-0" />
            <Button type="submit" aria-label="Send" disabled={!question.trim()} loading={ask.isPending}><Send className="size-4" /></Button>
          </div>
          <p className="mt-1 text-right text-xs text-slate-500">{question.length}/2000</p>
        </form>
      </section>
    </div>
  )
}
