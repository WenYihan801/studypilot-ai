import { ArrowLeft, ChevronLeft, ChevronRight, History, Layers, RotateCw, Trash2 } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, Badge, Button, Card, EmptyState, ErrorState, Input, Label, PageHeader, Spinner } from '@/components/ui'
import { DocumentPicker } from '@/features/quiz/QuizStudioPage'
import { useWorkspaceContext } from '@/features/workspaces/WorkspaceLayout'
import { useDeleteFlashSet, useDue, useFlashSet, useFlashSets, useGenerateFlashcards, useReviews, useUpdateMastery } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import type { Mastery } from '@/types/api'

const MASTERY_TONE = { NEW: 'slate', LEARNING: 'amber', MASTERED: 'green' } as const

export function FlashcardsPage() {
  const { workspace } = useWorkspaceContext()
  const navigate = useNavigate()
  const sets = useFlashSets(workspace.id)
  const due = useDue(workspace.id)
  const gen = useGenerateFlashcards(workspace.id)
  const del = useDeleteFlashSet(workspace.id)
  const [title, setTitle] = useState('')
  const [count, setCount] = useState(10)
  const [docIds, setDocIds] = useState<string[]>([])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const fs = await gen.mutateAsync({ title: title || undefined, count, document_ids: docIds.length ? docIds : undefined })
    navigate(`/app/flashcard-sets/${fs.id}`)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      <Card className="h-fit p-5">
        <h2 className="mb-4 font-semibold">Generate flashcards</h2>
        <form onSubmit={submit} className="space-y-4">
          <div><Label htmlFor="f-title" hint="(optional)">Title</Label><Input id="f-title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Key definitions" /></div>
          <div><Label htmlFor="f-count">Number of cards</Label><Input id="f-count" type="number" min={1} max={30} value={count} onChange={(e) => setCount(Math.max(1, Math.min(30, Number(e.target.value))))} /></div>
          <div><Label>Source documents</Label><DocumentPicker workspaceId={workspace.id} value={docIds} onChange={setDocIds} /></div>
          {gen.error && <Alert tone="error">{errorMessage(gen.error)}</Alert>}
          <Button type="submit" className="w-full" loading={gen.isPending}>{gen.isPending ? 'Creating cards…' : 'Generate flashcards'}</Button>
        </form>
      </Card>

      <section className="space-y-6">
        {due.data && due.data.length > 0 && (
          <Alert tone="info"><strong>{due.data.length}</strong> card{due.data.length === 1 ? '' : 's'} in this workspace still to master.</Alert>
        )}
        <div>
          <h2 className="mb-3 font-semibold">Flashcard sets</h2>
          {sets.isLoading ? <Spinner /> : sets.error ? <ErrorState message={errorMessage(sets.error)} onRetry={sets.refetch} /> : sets.data!.length === 0 ? (
            <EmptyState icon={<Layers className="size-6" />} title="No flashcards yet" description="Generate a set from your materials using the form." />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {sets.data!.map((s) => {
                const pct = s.card_count ? Math.round((100 * s.mastered_count) / s.card_count) : 0
                return (
                  <Card key={s.id} className="p-4">
                    <Link to={`/app/flashcard-sets/${s.id}`} className="font-medium hover:text-brand-700">{s.title}</Link>
                    <div className="mt-1 text-xs text-slate-500">{s.card_count} cards · {formatDate(s.created_at)}</div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Mastered">
                      <div className="h-full bg-emerald-500" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-xs text-slate-600">{s.mastered_count}/{s.card_count} mastered</span>
                      <span className="flex gap-1">
                        <Link to={`/app/flashcard-sets/${s.id}`}><Button size="sm">Review</Button></Link>
                        <Button size="sm" variant="ghost" aria-label={`Delete ${s.title}`} className="text-red-600" onClick={() => del.mutate(s.id)}><Trash2 className="size-4" /></Button>
                      </span>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

export function FlashcardReviewPage() {
  const { setId = '' } = useParams()
  const { data, isLoading, error } = useFlashSet(setId)
  const update = useUpdateMastery()
  const [onlyDue, setOnlyDue] = useState(false)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  const cards = useMemo(() => (data?.cards ?? []).filter((c) => !onlyDue || c.mastery_status !== 'MASTERED'), [data, onlyDue])
  const card = cards[Math.min(index, Math.max(cards.length - 1, 0))]
  const history = useReviews(showHistory && card ? card.id : null)

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorState message={errorMessage(error)} />

  const go = (d: number) => { setFlipped(false); setShowHistory(false); setIndex((i) => (i + d + cards.length) % cards.length) }
  const mark = async (status: Mastery) => {
    await update.mutateAsync({ id: card.id, status })
    if (cards.length > 1) go(1)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link to={`/app/workspaces/${data.workspace_id}/flashcards`} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="size-4" /> Flashcard sets</Link>
      <PageHeader title={data.title} description={`${data.cards.filter((c) => c.mastery_status === 'MASTERED').length}/${data.cards.length} mastered`}
        actions={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyDue} onChange={(e) => { setOnlyDue(e.target.checked); setIndex(0); setFlipped(false) }} /> Only cards to review</label>} />

      {!card ? (
        <EmptyState title="All cards mastered 🎉" description="Untick “Only cards to review” to go through the full set again." />
      ) : (
        <>
          <button type="button" onClick={() => setFlipped((f) => !f)} aria-label={flipped ? 'Show front' : 'Show answer'}
            className={cn('relative flex min-h-64 w-full flex-col items-center justify-center rounded-2xl border p-8 text-center shadow-sm transition-colors',
              flipped ? 'border-brand-200 bg-brand-50' : 'border-slate-200 bg-white hover:bg-slate-50')}>
            <span className="absolute left-4 top-4 text-xs font-medium uppercase tracking-wide text-slate-500">{flipped ? 'Answer' : 'Question'}</span>
            <span className="absolute right-4 top-4"><Badge tone={MASTERY_TONE[card.mastery_status]}>{card.mastery_status.toLowerCase()}</Badge></span>
            <p className={cn('text-lg', flipped ? 'text-slate-800' : 'font-medium text-slate-900')}>{flipped ? card.back : card.front}</p>
            <span className="absolute bottom-4 flex items-center gap-1 text-xs text-slate-500"><RotateCw className="size-3" /> Click to flip</span>
          </button>

          {flipped && card.source && (
            <p className="mt-3 rounded-lg bg-white p-3 text-xs text-slate-600 ring-1 ring-slate-200">
              Source: <span className="font-medium text-slate-800">{card.source.filename}{card.source.page_number ? `, p. ${card.source.page_number}` : ''}</span> — “{card.source.quote_text}”
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => go(-1)} aria-label="Previous card"><ChevronLeft className="size-4" /></Button>
              <span className="text-sm text-slate-600">{Math.min(index, cards.length - 1) + 1} / {cards.length}</span>
              <Button variant="secondary" size="sm" onClick={() => go(1)} aria-label="Next card"><ChevronRight className="size-4" /></Button>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" loading={update.isPending} onClick={() => mark('LEARNING')}>Still learning</Button>
              <Button size="sm" loading={update.isPending} onClick={() => mark('MASTERED')} className="bg-emerald-600 hover:bg-emerald-700">Mastered</Button>
            </div>
          </div>
          {update.error && <div className="mt-3"><Alert tone="error">{errorMessage(update.error)}</Alert></div>}

          <div className="mt-6">
            <button className="flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900" onClick={() => setShowHistory((s) => !s)}>
              <History className="size-4" /> {showHistory ? 'Hide' : 'Show'} review history
            </button>
            {showHistory && (
              <Card className="mt-2 p-3 text-sm">
                {history.isLoading ? <Spinner /> : !history.data?.length ? <p className="text-slate-500">Not reviewed yet.</p> : (
                  <ul className="space-y-1">{history.data.map((h) => (
                    <li key={h.id} className="flex justify-between"><span>{h.previous_status.toLowerCase()} → <strong>{h.new_status.toLowerCase()}</strong></span><span className="text-slate-500">{formatDate(h.reviewed_at, true)}</span></li>
                  ))}</ul>
                )}
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  )
}
