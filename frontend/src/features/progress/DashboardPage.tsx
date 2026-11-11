import { BookOpenCheck, FileText, FolderKanban, Layers, Sparkles, Trophy } from 'lucide-react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Button, Card, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from '@/components/ui'
import { useDashboard } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { relativeTime } from '@/lib/utils'

const ACTIVITY_LABEL: Record<string, string> = {
  chat: 'AI chat', summary: 'Summary', quiz_generated: 'Quiz created', quiz_submitted: 'Quiz completed',
  flashcards_generated: 'Flashcards created', flashcard_review: 'Flashcard review', document_uploaded: 'Upload',
}

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useDashboard()
  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorState message={errorMessage(error)} onRetry={refetch} />

  const isNew = data.total_workspaces === 0
  const chartData = data.activity_by_day.map((d) => ({ ...d, label: d.date.slice(5) }))

  return (
    <>
      <PageHeader title="Dashboard" description="Your study activity at a glance."
        actions={<Link to="/app/workspaces"><Button>Go to workspaces</Button></Link>} />

      {isNew && (
        <div className="mb-6">
          <EmptyState icon={<Sparkles className="size-6" />} title="Welcome to StudyPilot AI"
            description="Create a workspace for a course, upload your notes, then ask questions or generate a quiz."
            action={<Link to="/app/workspaces"><Button>Create your first workspace</Button></Link>} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Workspaces" value={data.total_workspaces} icon={<FolderKanban className="size-4" />} />
        <StatCard label="Documents" value={data.total_documents} icon={<FileText className="size-4" />} />
        <StatCard label="Study sessions" value={data.total_study_sessions} icon={<Sparkles className="size-4" />} />
        <StatCard label="Quizzes" value={data.total_quizzes} icon={<BookOpenCheck className="size-4" />} />
        <StatCard label="Avg. quiz score" value={data.average_quiz_score === null ? '—' : `${data.average_quiz_score}%`} icon={<Trophy className="size-4" />} />
        <StatCard label="Cards to review" value={data.flashcards_to_review} icon={<Layers className="size-4" />} />
      </div>

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Learning activity — last 14 days</h2>
            <Link to="/app/progress" className="text-sm font-medium text-brand-600">Details</Link>
          </div>
          <div className="h-56" aria-label="Activity per day chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} width={28} />
                <Tooltip cursor={{ fill: '#eef2ff' }} />
                <Bar dataKey="count" name="Activities" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold">Recent activity</h2>
          {data.recent_activity.length === 0 ? (
            <p className="text-sm text-slate-500">No activity yet.</p>
          ) : (
            <ul className="space-y-3">
              {data.recent_activity.map((a) => (
                <li key={a.id} className="text-sm">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium text-slate-800">{ACTIVITY_LABEL[a.activity_type] ?? a.activity_type}</span>
                    <span className="shrink-0 text-xs text-slate-500">{relativeTime(a.created_at)}</span>
                  </div>
                  <p className="truncate text-slate-600" title={a.description}>{a.description}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}
