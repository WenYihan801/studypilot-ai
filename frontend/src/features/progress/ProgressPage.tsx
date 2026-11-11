import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, EmptyState, ErrorState, PageHeader, Spinner } from '@/components/ui'
import { useDashboard, useUsage } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'

const MASTERY_COLORS = { NEW: '#94a3b8', LEARNING: '#f59e0b', MASTERED: '#10b981' }

export function ProgressPage() {
  const dash = useDashboard()
  const usage = useUsage()
  if (dash.isLoading || usage.isLoading) return <Spinner />
  if (dash.error || !dash.data) return <ErrorState message={errorMessage(dash.error)} onRetry={dash.refetch} />
  const d = dash.data
  const scores = d.quiz_scores.map((s, i) => ({ ...s, n: i + 1, label: formatDate(s.submitted_at) }))
  const mastery = Object.entries(d.flashcard_mastery).map(([name, value]) => ({ name, value }))
  const totalCards = mastery.reduce((a, b) => a + b.value, 0)

  return (
    <>
      <PageHeader title="Learning progress" description="Quiz performance, flashcard mastery and AI usage — all from your real activity." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold">Quiz scores (last 10 attempts)</h2>
          {scores.length === 0 ? <EmptyState title="No quiz attempts yet" description="Complete a quiz to see your score trend." /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={scores}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="n" tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} width={32} unit="%" />
                  <Tooltip formatter={(v) => [`${v}%`, 'Score']} labelFormatter={(_, p) => p?.[0]?.payload?.title ?? ''} />
                  <Line type="monotone" dataKey="score" stroke="#4f46e5" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold">Flashcard mastery</h2>
          {totalCards === 0 ? <EmptyState title="No flashcards yet" description="Generate flashcards from a workspace to track mastery." /> : (
            <div className="flex flex-col items-center gap-4 sm:flex-row">
              <div className="h-56 w-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={mastery} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                      {mastery.map((m) => <Cell key={m.name} fill={MASTERY_COLORS[m.name as keyof typeof MASTERY_COLORS]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2 text-sm">
                {mastery.map((m) => (
                  <li key={m.name} className="flex items-center gap-2">
                    <span className="size-3 rounded-sm" style={{ background: MASTERY_COLORS[m.name as keyof typeof MASTERY_COLORS] }} />
                    <span className="w-24 text-slate-700">{m.name.charAt(0) + m.name.slice(1).toLowerCase()}</span>
                    <span className="font-medium">{m.value}</span>
                    <span className="text-slate-500">({Math.round((100 * m.value) / totalCards)}%)</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-1 text-sm font-semibold">AI usage — last 30 days</h2>
          {usage.data && (
            <p className="mb-4 text-sm text-slate-600">
              Today: <strong>{usage.data.requests_today}</strong> / {usage.data.daily_limit} requests · {usage.data.tokens_today.toLocaleString()} tokens ·
              estimated paid-tier cost (30d): ${usage.data.estimated_cost_30d.toFixed(4)} · provider: {usage.data.provider}
            </p>
          )}
          {usage.data && usage.data.by_day.length > 0 ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={usage.data.by_day.map((x) => ({ ...x, label: x.date.slice(5) }))}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#64748b' }} tickLine={false} axisLine={false} width={28} />
                  <Tooltip cursor={{ fill: '#eef2ff' }} />
                  <Bar dataKey="requests" name="AI requests" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="text-sm text-slate-500">No AI usage recorded yet.</p>}
        </Card>
      </div>
    </>
  )
}
