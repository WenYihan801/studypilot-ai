import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Alert, Button, Card, Dialog, Input, Label, PageHeader, Spinner } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { useDeleteAccount, useMe, useUpdateMe, useUsage } from '@/hooks/queries'
import { errorMessage } from '@/lib/api'
import { supabase } from '@/lib/supabase'

export function SettingsPage() {
  const me = useMe()
  const usage = useUsage()
  const del = useDeleteAccount()
  const { signOut } = useAuth()
  const [password, setPassword] = useState('')
  const [pwMsg, setPwMsg] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmText, setConfirmText] = useState('')

  async function changePassword(e: FormEvent) {
    e.preventDefault()
    if (password.length < 8) return setPwMsg({ tone: 'error', text: 'Password must be at least 8 characters.' })
    const { error } = await supabase.auth.updateUser({ password })
    setPwMsg(error ? { tone: 'error', text: error.message } : { tone: 'success', text: 'Password updated.' })
    setPassword('')
  }

  if (me.isLoading) return <Spinner />

  return (
    <div className="max-w-2xl">
      <PageHeader title="Settings" />
      <div className="space-y-6">
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Profile</h2>
          <ProfileForm key={me.data?.id} email={me.data?.email ?? ''} initialName={me.data?.display_name ?? ''} />
        </Card>

        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Password</h2>
          <form onSubmit={changePassword} className="space-y-4">
            <div><Label htmlFor="s-pw">New password</Label><Input id="s-pw" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            {pwMsg && <Alert tone={pwMsg.tone}>{pwMsg.text}</Alert>}
            <Button type="submit" variant="secondary">Change password</Button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="mb-2 font-semibold">AI usage & limits</h2>
          {usage.data ? (
            <>
              <div className="mb-1 flex justify-between text-sm"><span>Requests today</span><span className="font-medium">{usage.data.requests_today} / {usage.data.daily_limit}</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand-600" style={{ width: `${Math.min(100, (100 * usage.data.requests_today) / usage.data.daily_limit)}%` }} /></div>
              <p className="mt-2 text-xs text-slate-500">The daily limit resets at 00:00 UTC. Document embedding does not count towards it.</p>
            </>
          ) : <Spinner />}
        </Card>

        <Card className="p-5">
          <h2 className="mb-2 font-semibold">Privacy</h2>
          <p className="text-sm text-slate-700">Uploaded materials and questions are sent to Google Gemini for processing. On the free API tier, Google may use that content to improve its products. Use public or self-made materials. <Link to="/privacy" className="font-medium text-brand-600">Read more</Link></p>
        </Card>

        <Card className="border-red-200 p-5">
          <h2 className="mb-2 font-semibold text-red-700">Delete account</h2>
          <p className="mb-4 text-sm text-slate-700">Permanently deletes all your workspaces, files, vectors, chats, quizzes, flashcards, usage history and your login.</p>
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>Delete my account</Button>
        </Card>
      </div>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Delete account permanently?"
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="danger" disabled={confirmText !== 'DELETE'} loading={del.isPending}
            onClick={async () => { await del.mutateAsync(); await signOut() }}>Delete everything</Button>
        </>}>
        <p className="mb-3 text-sm text-slate-700">This cannot be undone. Type <strong>DELETE</strong> to confirm.</p>
        <Input aria-label="Type DELETE to confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        {del.error && <div className="mt-3"><Alert tone="error">{errorMessage(del.error)}</Alert></div>}
      </Dialog>
    </div>
  )
}

function ProfileForm({ email, initialName }: { email: string; initialName: string }) {
  const update = useUpdateMe()
  const [name, setName] = useState(initialName)
  const [saved, setSaved] = useState(false)

  async function saveProfile(e: FormEvent) {
    e.preventDefault()
    await update.mutateAsync(name)
    setSaved(true)
    setTimeout(() => setSaved(false), 2500)
  }

  return (
    <form onSubmit={saveProfile} className="space-y-4">
      <div><Label htmlFor="s-email">Email</Label><Input id="s-email" value={email} disabled /></div>
      <div><Label htmlFor="s-name">Display name</Label><Input id="s-name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></div>
      {update.error && <Alert tone="error">{errorMessage(update.error)}</Alert>}
      {saved && <Alert tone="success">Profile saved.</Alert>}
      <Button type="submit" loading={update.isPending}>Save profile</Button>
    </form>
  )
}
