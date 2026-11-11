import { ArrowLeft, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate, useOutletContext, useParams } from 'react-router'
import { Button, ErrorState, Spinner } from '@/components/ui'
import { useWorkspace } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Workspace } from '@/types/api'
import { DeleteWorkspaceDialog, WorkspaceFormDialog } from './WorkspacesPage'

const TABS = [
  { to: '', label: 'Documents', end: true },
  { to: 'chat', label: 'AI Chat', end: false },
  { to: 'quizzes', label: 'Quiz Studio', end: false },
  { to: 'flashcards', label: 'Flashcards', end: false },
]

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspaceContext() {
  return useOutletContext<{ workspace: Workspace }>()
}

export function WorkspaceLayout() {
  const { workspaceId = '' } = useParams()
  const navigate = useNavigate()
  const { data: ws, isLoading, error, refetch } = useWorkspace(workspaceId)
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)

  if (isLoading) return <Spinner />
  if (error || !ws) return <ErrorState message={errorMessage(error)} onRetry={refetch} />

  return (
    <>
      <Link to="/app/workspaces" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="size-4" /> All workspaces</Link>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{ws.name}</h1>
          {ws.description && <p className="mt-1 text-sm text-slate-600">{ws.description}</p>}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setEditing(true)}><Pencil className="size-4" /> Edit</Button>
          <Button variant="secondary" size="sm" onClick={() => setDeleting(true)} className="text-red-600"><Trash2 className="size-4" /> Delete</Button>
        </div>
      </div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200" aria-label="Workspace sections">
        {TABS.map((t) => (
          <NavLink key={t.label} to={t.to} end={t.end}
            className={({ isActive }) => cn('-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium',
              isActive ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-600 hover:text-slate-900')}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={{ workspace: ws }} />
      {editing && <WorkspaceFormDialog open workspace={ws} onClose={() => setEditing(false)} />}
      <DeleteWorkspaceDialog workspace={deleting ? ws : null} onClose={() => setDeleting(false)} onDeleted={() => navigate('/app/workspaces')} />
    </>
  )
}
