import { FileText, Loader2, RefreshCw, ScrollText, Trash2, UploadCloud } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router'
import { Alert, Badge, Button, Card, Dialog, EmptyState, ErrorState, Spinner } from '@/components/ui'
import { useWorkspaceContext } from '@/features/workspaces/WorkspaceLayout'
import { useDocumentAction, useDocuments, useUploadDocument } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { ACCEPTED_EXTENSIONS, cn, formatBytes, formatDate, MAX_UPLOAD_MB, validateFile } from '@/lib/utils'
import type { DocStatus, DocumentItem } from '@/types/api'

export function StatusBadge({ status }: { status: DocStatus }) {
  const map = {
    UPLOADED: { tone: 'slate', label: 'Uploaded' },
    PROCESSING: { tone: 'amber', label: 'Processing' },
    READY: { tone: 'green', label: 'Ready' },
    FAILED: { tone: 'red', label: 'Failed' },
  } as const
  const { tone, label } = map[status]
  return <Badge tone={tone}>{status === 'PROCESSING' && <Loader2 className="size-3 animate-spin" />}{label}</Badge>
}

export function DocumentsPanel() {
  const { workspace } = useWorkspaceContext()
  const { data, isLoading, error, refetch } = useDocuments(workspace.id)
  const upload = useUploadDocument(workspace.id)
  const action = useDocumentAction(workspace.id)
  const input = useRef<HTMLInputElement>(null)
  const [messages, setMessages] = useState<{ tone: 'error' | 'success'; text: string }[]>([])
  const [dragging, setDragging] = useState(false)
  const [toDelete, setToDelete] = useState<DocumentItem | null>(null)

  async function handleFiles(files: FileList | File[]) {
    const out: typeof messages = []
    for (const file of Array.from(files)) {
      const problem = validateFile(file)
      if (problem) { out.push({ tone: 'error', text: problem }); continue }
      try {
        await upload.mutateAsync(file)
        out.push({ tone: 'success', text: `${file.name} uploaded — processing in the background.` })
      } catch (e) {
        out.push({ tone: 'error', text: `${file.name}: ${errorMessage(e)}` })
      }
    }
    setMessages(out)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-6">
      <div onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
        className={cn('rounded-xl border-2 border-dashed bg-white p-8 text-center transition-colors', dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300')}>
        <UploadCloud className="mx-auto size-8 text-slate-400" aria-hidden />
        <p className="mt-3 text-sm font-medium text-slate-800">Drag & drop files here, or</p>
        <Button className="mt-3" onClick={() => input.current?.click()} loading={upload.isPending}>Choose files</Button>
        <p className="mt-3 text-xs text-slate-500">PDF, DOCX, TXT, Markdown · up to {MAX_UPLOAD_MB} MB each · files are private to you and sent to Gemini for processing</p>
        <input ref={input} type="file" multiple hidden accept={ACCEPTED_EXTENSIONS.join(',')} aria-label="Upload documents"
          onChange={(e) => { if (e.target.files) handleFiles(e.target.files); e.target.value = '' }} />
      </div>

      {messages.length > 0 && <div className="space-y-2">{messages.map((m, i) => <Alert key={i} tone={m.tone}>{m.text}</Alert>)}</div>}

      {isLoading ? <Spinner /> : error ? <ErrorState message={errorMessage(error)} onRetry={refetch} /> : data!.length === 0 ? (
        <EmptyState icon={<FileText className="size-6" />} title="No documents yet" description="Upload lecture notes, slides exported to PDF or papers to start." />
      ) : (
        <Card className="divide-y divide-slate-200">
          {data!.map((doc) => (
            <div key={doc.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <FileText className="hidden size-5 shrink-0 text-slate-400 sm:block" aria-hidden />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium text-slate-900">{doc.filename}</span>
                  <StatusBadge status={doc.status} />
                </div>
                <div className="mt-0.5 text-xs text-slate-500">
                  {formatBytes(doc.size_bytes)} · {doc.page_count ? `${doc.page_count} pages · ` : ''}{doc.chunk_count} chunks · {formatDate(doc.created_at)}
                </div>
                {doc.status === 'FAILED' && doc.error_message && <p className="mt-1 text-xs text-red-700">{doc.error_message}</p>}
              </div>
              <div className="flex gap-2">
                {doc.status === 'READY' && (
                  <Link to={`/app/documents/${doc.id}/summary`}><Button size="sm" variant="secondary"><ScrollText className="size-4" /> Summary</Button></Link>
                )}
                {(doc.status === 'FAILED' || doc.status === 'PROCESSING' || doc.status === 'UPLOADED') && (
                  <Button size="sm" variant="secondary" onClick={() => action.mutate({ id: doc.id, action: 'process' })}
                    title="Re-run text extraction and indexing"><RefreshCw className="size-4" /> Reprocess</Button>
                )}
                <Button size="sm" variant="ghost" aria-label={`Delete ${doc.filename}`} onClick={() => setToDelete(doc)} className="text-red-600"><Trash2 className="size-4" /></Button>
              </div>
            </div>
          ))}
        </Card>
      )}
      {action.error && <Alert tone="error">{errorMessage(action.error)}</Alert>}

      <Dialog open={Boolean(toDelete)} onClose={() => setToDelete(null)} title="Delete document?"
        footer={<>
          <Button variant="secondary" onClick={() => setToDelete(null)}>Cancel</Button>
          <Button variant="danger" loading={action.isPending}
            onClick={async () => { await action.mutateAsync({ id: toDelete!.id, action: 'delete' }); setToDelete(null) }}>Delete</Button>
        </>}>
        <p className="text-sm text-slate-700"><strong>{toDelete?.filename}</strong>, its stored file, vectors and summary will be deleted. Past chat citations to it will be removed.</p>
      </Dialog>
    </div>
  )
}
