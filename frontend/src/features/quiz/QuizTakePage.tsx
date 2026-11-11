import { ArrowLeft, CheckCircle2, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, Badge, Button, Card, ErrorState, PageHeader, Spinner, Textarea } from '@/components/ui'
import { useAttemptResult, useQuiz, useStartAttempt, useSubmitAttempt } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import type { QuizQuestion } from '@/types/api'

function QuestionInput({ q, value, onChange }: { q: QuizQuestion; value: string; onChange: (v: string) => void }) {
  if (q.type === 'short_answer') {
    return <Textarea aria-label={`Answer to question ${q.position + 1}`} rows={3} maxLength={2000} value={value} onChange={(e) => onChange(e.target.value)} placeholder="Type your answer…" />
  }
  return (
    <div role="radiogroup" className="space-y-2">
      {q.options.map((opt) => (
        <label key={opt} className={cn('flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors',
          value === opt ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:bg-slate-50')}>
          <input type="radio" name={q.id} className="mt-0.5" checked={value === opt} onChange={() => onChange(opt)} />
          <span>{opt}</span>
        </label>
      ))}
    </div>
  )
}

export function QuizTakePage() {
  const { quizId = '' } = useParams()
  const navigate = useNavigate()
  const quiz = useQuiz(quizId)
  const start = useStartAttempt()
  const submit = useSubmitAttempt()
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const started = useRef(false)

  useEffect(() => {
    if (!started.current && quiz.data) { started.current = true; start.mutate(quiz.data.id) }
  }, [quiz.data, start])

  if (quiz.isLoading) return <Spinner />
  if (quiz.error || !quiz.data) return <ErrorState message={errorMessage(quiz.error)} />
  const q = quiz.data
  const answered = q.questions.filter((x) => (answers[x.id] ?? '').trim()).length

  async function onSubmit() {
    if (!start.data) return
    const res = await submit.mutateAsync({ id: start.data.id, answers })
    navigate(`/app/quiz-attempts/${res.attempt.id}`)
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={`/app/workspaces/${q.workspace_id}/quizzes`} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="size-4" /> Quiz Studio</Link>
      <PageHeader title={q.title} description={`${q.questions.length} questions · answer all, then submit for instant grading.`} />
      <div className="space-y-4">
        {q.questions.map((x) => (
          <Card key={x.id} className="p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <h2 className="text-sm font-medium text-slate-900"><span className="mr-2 text-slate-500">{x.position + 1}.</span>{x.question}</h2>
              <Badge>{x.difficulty}</Badge>
            </div>
            <QuestionInput q={x} value={answers[x.id] ?? ''} onChange={(v) => setAnswers((a) => ({ ...a, [x.id]: v }))} />
          </Card>
        ))}
      </div>
      {(start.error || submit.error) && <div className="mt-4"><Alert tone="error">{errorMessage(start.error ?? submit.error)}</Alert></div>}
      <div className="sticky bottom-0 mt-6 flex items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 py-4">
        <span className="text-sm text-slate-600">{answered} / {q.questions.length} answered</span>
        <Button onClick={onSubmit} loading={submit.isPending} disabled={!start.data}>Submit answers</Button>
      </div>
    </div>
  )
}

export function QuizResultPage() {
  const { attemptId = '' } = useParams()
  const { data, isLoading, error } = useAttemptResult(attemptId)
  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorState message={errorMessage(error)} />
  const correct = data.items.filter((i) => i.is_correct).length
  const score = data.attempt.score ?? 0

  return (
    <div className="mx-auto max-w-3xl">
      {data.quiz.workspace_id && <Link to={`/app/workspaces/${data.quiz.workspace_id}/quizzes`} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="size-4" /> Quiz Studio</Link>}
      <PageHeader title={`Results: ${data.quiz.title}`} description={`Submitted ${formatDate(data.attempt.submitted_at, true)}`}
        actions={<Link to={`/app/quizzes/${data.quiz.id}/take`}><Button variant="secondary">Retake quiz</Button></Link>} />
      <Card className="mb-6 flex items-center gap-6 p-6">
        <div className={cn('flex size-20 items-center justify-center rounded-full text-2xl font-semibold', score >= 70 ? 'bg-emerald-50 text-emerald-700' : score >= 40 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700')}>{Math.round(score)}%</div>
        <div><div className="text-lg font-semibold">{correct} of {data.items.length} correct</div>
          <p className="text-sm text-slate-600">{score >= 70 ? 'Great work — review the explanations to lock it in.' : 'Review the explanations and source passages below, then retake.'}</p></div>
      </Card>
      <div className="space-y-4">
        {data.items.map((it) => (
          <Card key={it.question_id} className={cn('border-l-4 p-5', it.is_correct ? 'border-l-emerald-500' : 'border-l-red-500')}>
            <div className="mb-2 flex items-start gap-2">
              {it.is_correct ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" aria-label="Correct" /> : <XCircle className="mt-0.5 size-5 shrink-0 text-red-600" aria-label="Incorrect" />}
              <h2 className="text-sm font-medium">{it.position + 1}. {it.question}</h2>
            </div>
            <dl className="ml-7 space-y-2 text-sm">
              <div><dt className="inline font-medium text-slate-600">Your answer: </dt><dd className={cn('inline', it.is_correct ? 'text-emerald-700' : 'text-red-700')}>{it.your_answer || <em>No answer</em>}</dd></div>
              {!it.is_correct && <div><dt className="inline font-medium text-slate-600">Correct answer: </dt><dd className="inline text-slate-900">{it.correct_answer}</dd></div>}
              {it.type === 'short_answer' && it.feedback && <div><dt className="inline font-medium text-slate-600">Feedback: </dt><dd className="inline">{it.feedback}</dd></div>}
              <div><dt className="font-medium text-slate-600">Explanation</dt><dd className="text-slate-700">{it.explanation}</dd></div>
              {it.sources.length > 0 && (
                <div><dt className="font-medium text-slate-600">Study material</dt>
                  {it.sources.map((s) => (
                    <dd key={s.chunk_id} className="mt-1 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">
                      <span className="font-medium text-slate-800">{s.filename}{s.page_number ? `, p. ${s.page_number}` : ''}</span> — “{s.quote_text}”
                    </dd>
                  ))}
                </div>
              )}
            </dl>
          </Card>
        ))}
      </div>
    </div>
  )
}
