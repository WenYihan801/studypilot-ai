import { BookOpenCheck, Play, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { Alert, Badge, Button, Card, EmptyState, ErrorState, Input, Label, Select, Spinner } from '@/components/ui'
import { useWorkspaceContext } from '@/features/workspaces/WorkspaceLayout'
import { useDeleteQuiz, useDocuments, useGenerateQuiz, useQuizzes } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type { Difficulty, QuestionType } from '@/types/api'

const TYPE_LABEL: Record<QuestionType, string> = { multiple_choice: 'Multiple choice', true_false: 'True / False', short_answer: 'Short answer' }

export function DocumentPicker({ workspaceId, value, onChange }: { workspaceId: string; value: string[]; onChange: (ids: string[]) => void }) {
  const docs = useDocuments(workspaceId)
  const ready = docs.data?.filter((d) => d.status === 'READY') ?? []
  if (ready.length === 0) return <p className="text-sm text-amber-700">No ready documents yet — upload and wait for processing.</p>
  return (
    <fieldset className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
      <legend className="sr-only">Documents</legend>
      {ready.map((d) => (
        <label key={d.id} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={value.includes(d.id)} onChange={(e) => onChange(e.target.checked ? [...value, d.id] : value.filter((x) => x !== d.id))} />
          <span className="truncate">{d.filename}</span>
        </label>
      ))}
      <p className="pt-1 text-xs text-slate-500">{value.length === 0 ? 'None selected = use all documents in this workspace.' : `${value.length} selected`}</p>
    </fieldset>
  )
}

export function QuizStudioPage() {
  const { workspace } = useWorkspaceContext()
  const navigate = useNavigate()
  const quizzes = useQuizzes(workspace.id)
  const gen = useGenerateQuiz(workspace.id)
  const del = useDeleteQuiz(workspace.id)
  const [title, setTitle] = useState('')
  const [count, setCount] = useState(5)
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [types, setTypes] = useState<QuestionType[]>(['multiple_choice', 'true_false'])
  const [docIds, setDocIds] = useState<string[]>([])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const quiz = await gen.mutateAsync({ title: title || undefined, num_questions: count, difficulty, types, document_ids: docIds.length ? docIds : undefined })
    navigate(`/app/quizzes/${quiz.id}/take`)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
      <Card className="h-fit p-5">
        <h2 className="mb-4 font-semibold">Generate a quiz</h2>
        <form onSubmit={submit} className="space-y-4">
          <div><Label htmlFor="q-title" hint="(optional)">Title</Label><Input id="q-title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Week 3 revision" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label htmlFor="q-count">Questions</Label><Input id="q-count" type="number" min={1} max={20} value={count} onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value))))} /></div>
            <div><Label htmlFor="q-diff">Difficulty</Label>
              <Select id="q-diff" value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
                <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option><option value="mixed">Mixed</option>
              </Select></div>
          </div>
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-slate-700">Question types</legend>
            <div className="space-y-1">
              {(Object.keys(TYPE_LABEL) as QuestionType[]).map((t) => (
                <label key={t} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={types.includes(t)} onChange={(e) => setTypes(e.target.checked ? [...types, t] : types.filter((x) => x !== t))} />
                  {TYPE_LABEL[t]}
                </label>
              ))}
            </div>
          </fieldset>
          <div><Label>Source documents</Label><DocumentPicker workspaceId={workspace.id} value={docIds} onChange={setDocIds} /></div>
          {gen.error && <Alert tone="error">{errorMessage(gen.error)}</Alert>}
          <Button type="submit" className="w-full" loading={gen.isPending} disabled={types.length === 0}>
            {gen.isPending ? 'Generating questions…' : 'Generate quiz'}
          </Button>
          <p className="text-xs text-slate-500">Every question is validated and linked to the passage it came from.</p>
        </form>
      </Card>

      <section>
        <h2 className="mb-3 font-semibold">Your quizzes</h2>
        {quizzes.isLoading ? <Spinner /> : quizzes.error ? <ErrorState message={errorMessage(quizzes.error)} onRetry={quizzes.refetch} /> : quizzes.data!.length === 0 ? (
          <EmptyState icon={<BookOpenCheck className="size-6" />} title="No quizzes yet" description="Generate one from your materials using the form." />
        ) : (
          <Card className="divide-y divide-slate-200">
            {quizzes.data!.map((q) => (
              <div key={q.id} className="flex items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{q.title}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>{q.question_count} questions · {formatDate(q.created_at)}</span>
                    {q.best_score !== null ? <Badge tone={q.best_score >= 70 ? 'green' : 'amber'}>Best {q.best_score}%</Badge> : <Badge>Not attempted</Badge>}
                  </div>
                </div>
                <Button size="sm" onClick={() => navigate(`/app/quizzes/${q.id}/take`)}><Play className="size-4" /> {q.attempt_count ? 'Retake' : 'Start'}</Button>
                <Button size="sm" variant="ghost" aria-label={`Delete ${q.title}`} className="text-red-600" onClick={() => del.mutate(q.id)}><Trash2 className="size-4" /></Button>
              </div>
            ))}
          </Card>
        )}
      </section>
    </div>
  )
}
