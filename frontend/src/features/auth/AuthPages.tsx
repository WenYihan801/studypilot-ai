import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { Alert, Button, Card, Input, Label } from '@/components/ui'
import { Logo } from '@/app/Logo'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { useAuth } from './AuthProvider'

function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <Link to="/" className="mb-8"><Logo /></Link>
      <Card className="w-full max-w-sm p-6">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-1 mb-6 text-sm text-slate-600">{subtitle}</p>
        {!supabaseConfigured && (
          <div className="mb-4"><Alert tone="warning">Supabase is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.</Alert></div>
        )}
        {children}
      </Card>
      <p className="mt-6 text-sm text-slate-600">{footer}</p>
    </div>
  )
}

export function LoginPage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (session) return <Navigate to="/app" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setBusy(false)
    if (error) setError(error.message)
    else navigate('/app')
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to continue studying." footer={<>No account? <Link className="font-medium text-brand-600" to="/register">Create one</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <div><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div>
          <div className="flex items-center justify-between"><Label htmlFor="password">Password</Label>
            <Link to="/forgot-password" className="mb-1.5 text-xs font-medium text-brand-600">Forgot password?</Link></div>
          <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <Alert tone="error">{error}</Alert>}
        <Button type="submit" className="w-full" loading={busy}>Sign in</Button>
      </form>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { session } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  if (session) return <Navigate to="/app" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (password.length < 8) return setError('Password must be at least 8 characters.')
    setBusy(true)
    setError(null)
    const { data, error } = await supabase.auth.signUp({
      email, password, options: { data: { display_name: name }, emailRedirectTo: `${window.location.origin}/app` },
    })
    setBusy(false)
    if (error) setError(error.message)
    else if (!data.session) setDone(true) // email confirmation required
  }

  return (
    <AuthShell title="Create your account" subtitle="Free for students. Your materials stay private to you." footer={<>Already have an account? <Link className="font-medium text-brand-600" to="/login">Sign in</Link></>}>
      {done ? (
        <Alert tone="success">Check your inbox at <strong>{email}</strong> to confirm your account, then sign in.</Alert>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div><Label htmlFor="name">Display name</Label><Input id="name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div><Label htmlFor="password" hint="(min. 8 characters)">Password</Label><Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          <p className="text-xs text-slate-500">By signing up you acknowledge that uploaded materials are sent to a third-party AI provider (Google Gemini) for processing. See <Link to="/privacy" className="underline">Privacy</Link>.</p>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" className="w-full" loading={busy}>Create account</Button>
        </form>
      )}
    </AuthShell>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/reset-password` })
    setBusy(false)
    if (error) setError(error.message)
    else setSent(true)
  }

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a secure reset link." footer={<Link className="font-medium text-brand-600" to="/login">Back to sign in</Link>}>
      {sent ? <Alert tone="success">If an account exists for {email}, a reset link is on its way.</Alert> : (
        <form onSubmit={submit} className="space-y-4">
          <div><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" className="w-full" loading={busy}>Send reset link</Button>
        </form>
      )}
    </AuthShell>
  )
}

export function ResetPasswordPage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (password.length < 8) return setError('Password must be at least 8 characters.')
    setBusy(true)
    const { error } = await supabase.auth.updateUser({ password })
    setBusy(false)
    if (error) setError(error.message)
    else navigate('/app')
  }

  return (
    <AuthShell title="Choose a new password" subtitle="Enter a new password for your account." footer={<Link className="font-medium text-brand-600" to="/login">Back to sign in</Link>}>
      {!session ? <Alert tone="warning">This reset link is invalid or has expired. Request a new one.</Alert> : (
        <form onSubmit={submit} className="space-y-4">
          <div><Label htmlFor="password">New password</Label><Input id="password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" className="w-full" loading={busy}>Update password</Button>
        </form>
      )}
    </AuthShell>
  )
}
