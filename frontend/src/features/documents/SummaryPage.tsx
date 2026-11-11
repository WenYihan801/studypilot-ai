import { ArrowLeft, RefreshCw, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { Alert, Badge, Button, Card, EmptyState, ErrorState, PageHeader, Spinner } from '@/components/ui'
import { useCachedSummary, useDocument, useGenerateSummary } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'

function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
        <span className="flex size-6 items-center justify-center rounded-full bg-brand-50 text-xs text-brand-700">{n}</span>{title}
      </h2>
      <div className="text-sm text-slate-700">{children}</div>
    </Card>
  )
}

const List = ({ items }: { items: string[] }) =>
  items.length ? <ul className="list-disc space-y-1 pl-5">{items.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="text-slate-500">None identified.</p>

export function SummaryPage() {
  const { documentId = '' } = useParams()
  const doc = useDocument(documentId)
  const cached = useCachedSummary(documentId)
  const gen = useGenerateSummary(documentId)
  const data = gen.data ?? cached.data

  if (doc.isLoading || cached.isLoading) return <Spinner />
  if (doc.error) return <ErrorState message={errorMessage(doc.error)} />
  const s = data?.summary

  return (
    <>
      <Link to={`/app/workspaces/${doc.data!.workspace_id}`} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="size-4" /> Back to documents</Link>
      <PageHeader title={doc.data!.filename} description="AI document summary"
        actions={s && <Button variant="secondary" loading={gen.isPending} onClick={() => gen.mutate(true)}><RefreshCw className="size-4" /> Regenerate</Button>} />
      {gen.error && <div className="mb-4"><Alert tone="error">{errorMessage(gen.error)}</Alert></div>}

      {!s ? (
        gen.isPending ? <Spinner label="Summarising section by section… this can take a minute for long documents." /> : (
          <EmptyState icon={<Sparkles className="size-6" />} title="No summary yet"
            description="Long documents are summarised section by section, then combined. The result is cached so it only costs one generation."
            action={<Button onClick={() => gen.mutate(false)}>Generate summary</Button>} />
        )
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            {data!.cached && <Badge>Cached</Badge>}
            <span>Generated {formatDate(data!.created_at, true)}{data!.model_name ? ` · ${data!.model_name}` : ''}</span>
          </div>
          <Section n={1} title="Document overview"><p className="leading-relaxed">{s.overview}</p></Section>
          <Section n={2} title="Main topics"><List items={s.main_topics} /></Section>
          <Section n={3} title="Key concepts">
            {s.key_concepts.length ? <dl className="space-y-2">{s.key_concepts.map((c, i) => <div key={i}><dt className="font-medium text-slate-900">{c.name}</dt><dd>{c.explanation}</dd></div>)}</dl> : <p className="text-slate-500">None identified.</p>}
          </Section>
          <Section n={4} title="Important definitions">
            {s.important_definitions.length ? <dl className="space-y-2">{s.important_definitions.map((d, i) => <div key={i}><dt className="font-medium text-slate-900">{d.term}</dt><dd>{d.definition}</dd></div>)}</dl> : <p className="text-slate-500">None identified.</p>}
          </Section>
          <Section n={5} title="Important arguments"><List items={s.important_arguments} /></Section>
          <Section n={6} title="Key takeaways"><List items={s.key_takeaways} /></Section>
          <Section n={7} title="Revision checklist">
            <ul className="space-y-1">{s.revision_checklist.map((x, i) => <li key={i} className="flex gap-2"><input type="checkbox" aria-label={x} className="mt-1" /> {x}</li>)}</ul>
          </Section>
          <Section n={8} title="Source references">
            <ul className="space-y-1">{s.source_references.map((r, i) => <li key={i}>{r.filename}{r.location ? ` — ${r.location}` : ''}</li>)}</ul>
          </Section>
        </div>
      )}
    </>
  )
}
