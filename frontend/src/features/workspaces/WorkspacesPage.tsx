import { FolderKanban, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Alert, Button, Card, Dialog, EmptyState, ErrorState, Input, Label, PageHeader, Spinner, Textarea } from '@/components/ui'
import { useDeleteWorkspace, useSaveWorkspace, useWorkspaces } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type { Workspace } from '@/types/api'

export function WorkspaceFormDialog({ open, onClose, workspace }: { open: boolean; onClose: () => void; workspace?: Workspace }) {
  const save = useSaveWorkspace()
  const [name, setName] = useState(workspace?.name ?? '')
  const [description, setDescription] = useState(workspace?.description ?? '')

  async function submit(e: FormEvent) {
    e.preventDefault()
    await save.mutateAsync({ id: workspace?.id, name, description })
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title={workspace ? 'Edit workspace' : 'New workspace'}
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button type="submit" form="ws-form" loading={save.isPending}>{workspace ? 'Save changes' : 'Create workspace'}</Button>
      </>}>
      <form id="ws-form" onSubmit={submit} className="space-y-4">
        <div><Label htmlFor="ws-name">Course name</Label>
          <Input id="ws-name" required maxLength={120} placeholder="e.g. Database Systems" value={name} onChange={(e) => setName(e.target.value)} autoFocus /></div>
        <div><Label htmlFor="ws-desc" hint="(optional)">Description</Label>
          <Textarea id="ws-desc" rows={3} maxLength={2000} placeholder="Module code, semester, focus areas…" value={description} onChange={(e) => setDescription(e.target.value)} /></div>
        {save.error && <Alert tone="error">{errorMessage(save.error)}</Alert>}
      </form>
    </Dialog>
  )
}

export function DeleteWorkspaceDialog({ workspace, onClose, onDeleted }: { workspace: Workspace | null; onClose: () => void; onDeleted?: () => void }) {
  const del = useDeleteWorkspace()
  return (
    <Dialog open={Boolean(workspace)} onClose={onClose} title="Delete workspace?"
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button variant="danger" loading={del.isPending} onClick={async () => { await del.mutateAsync(workspace!.id); onClose(); onDeleted?.() }}>Delete permanently</Button>
      </>}>
      <p className="text-sm text-slate-700">
        <strong>{workspace?.name}</strong> and everything in it — documents, stored files, vectors, chats, quizzes and flashcards — will be permanently deleted.
      </p>
      {del.error && <div className="mt-3"><Alert tone="error">{errorMessage(del.error)}</Alert></div>}
    </Dialog>
  )
}

export function WorkspacesPage() {
  const { data, isLoading, error, refetch } = useWorkspaces()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Workspace | null>(null)
  const [deleting, setDeleting] = useState<Workspace | null>(null)

  return (
    <>
      <PageHeader title="Workspaces" description="One workspace per course or research topic."
        actions={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> New workspace</Button>} />

      {isLoading ? <Spinner /> : error ? <ErrorState message={errorMessage(error)} onRetry={refetch} /> : data!.length === 0 ? (
        <EmptyState icon={<FolderKanban className="size-6" />} title="No workspaces yet" description="Create a workspace for each course, e.g. “Computer Networks”."
          action={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> New workspace</Button>} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data!.map((ws) => (
            <Card key={ws.id} className="group flex flex-col p-5 transition-shadow hover:shadow-md">
              <Link to={`/app/workspaces/${ws.id}`} className="flex-1">
                <h3 className="font-semibold text-slate-900 group-hover:text-brand-700">{ws.name}</h3>
                <p className="mt-1 line-clamp-2 min-h-10 text-sm text-slate-600">{ws.description || 'No description'}</p>
              </Link>
              <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                <span>{ws.document_count} document{ws.document_count === 1 ? '' : 's'} · {formatDate(ws.created_at)}</span>
                <span className="flex gap-1">
                  <button aria-label={`Edit ${ws.name}`} onClick={() => setEditing(ws)} className="rounded p-1.5 hover:bg-slate-100"><Pencil className="size-4" /></button>
                  <button aria-label={`Delete ${ws.name}`} onClick={() => setDeleting(ws)} className="rounded p-1.5 text-red-600 hover:bg-red-50"><Trash2 className="size-4" /></button>
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {creating && <WorkspaceFormDialog open onClose={() => setCreating(false)} />}
      {editing && <WorkspaceFormDialog open workspace={editing} onClose={() => setEditing(null)} />}
      <DeleteWorkspaceDialog workspace={deleting} onClose={() => setDeleting(null)} />
    </>
  )
}
