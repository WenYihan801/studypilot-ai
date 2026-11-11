import { BarChart3, FolderKanban, LayoutDashboard, LogOut, Menu, Settings, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation } from 'react-router'
import { Spinner } from '@/components/ui'
import { useAuth } from '@/features/auth/AuthProvider'
import { onServerWaking } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Logo } from './Logo'

const NAV = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/workspaces', label: 'Workspaces', icon: FolderKanban, end: false },
  { to: '/app/progress', label: 'Learning progress', icon: BarChart3, end: false },
  { to: '/app/settings', label: 'Settings', icon: Settings, end: false },
]

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
            isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-700 hover:bg-slate-100')}>
          <Icon className="size-4" aria-hidden /> {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppLayout() {
  const { session, loading, signOut } = useAuth()
  const [waking, setWaking] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  useEffect(() => onServerWaking(setWaking), [])

  if (loading) return <Spinner label="Loading your session…" />
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="px-3 py-4"><Logo /></div>
      <div className="flex-1 px-1"><NavItems onNavigate={() => setMobileOpen(false)} /></div>
      <div className="border-t border-slate-200 px-3 py-3">
        <div className="truncate text-xs text-slate-500" title={session.user.email}>{session.user.email}</div>
        <button onClick={signOut} className="mt-2 flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-900">
          <LogOut className="size-4" /> Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen lg:flex">
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white px-2 lg:block lg:sticky lg:top-0 lg:h-screen">{sidebar}</aside>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <Logo />
        <button aria-label="Open menu" onClick={() => setMobileOpen(true)} className="rounded p-2 hover:bg-slate-100"><Menu className="size-5" /></button>
      </header>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 bg-white px-2 shadow-xl">
            <button aria-label="Close menu" onClick={() => setMobileOpen(false)} className="absolute right-3 top-4 rounded p-1 hover:bg-slate-100"><X className="size-5" /></button>
            {sidebar}
          </div>
        </div>
      )}

      <main className="min-w-0 flex-1">
        {waking && (
          <div role="status" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-800">
            Waking up the server… free cloud instances sleep when idle, so the first request can take up to a minute.
          </div>
        )}
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8"><Outlet /></div>
      </main>
    </div>
  )
}
