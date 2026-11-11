import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabaseConfigured: true,
  supabase: {
    auth: {
      getSession: vi.fn(async () => ({ data: { session: { access_token: 'tok-123', user: { email: 'a@x.com' } } } })),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signOut: vi.fn(async () => ({})),
      signInWithPassword: vi.fn(async () => ({ error: { message: 'Invalid login credentials' } })),
    },
  },
}))

import { Markdown } from '@/components/Markdown'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { LoginPage } from '@/features/auth/AuthPages'
import { SourceCard } from '@/features/chat/ChatPage'
import { StatusBadge } from '@/features/documents/DocumentsPanel'
import { WorkspacesPage } from '@/features/workspaces/WorkspacesPage'
import { api, ApiError } from '@/lib/api'
import { validateFile } from '@/lib/utils'

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider><MemoryRouter>{ui}</MemoryRouter></AuthProvider>
    </QueryClientProvider>,
  )
}

function mockFetch(handler: (url: string, init?: RequestInit) => { status?: number; body?: unknown }) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const { status = 200, body } = handler(url, init)
    return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

beforeEach(() => vi.unstubAllGlobals())
afterEach(() => vi.restoreAllMocks())

describe('api client', () => {
  it('sends the Supabase access token and parses JSON', async () => {
    const f = mockFetch(() => ({ body: [{ id: 'w1' }] }))
    const data = await api<{ id: string }[]>('/workspaces')
    expect(data[0].id).toBe('w1')
    const [url, init] = f.mock.calls[0]
    expect(url).toMatch(/\/api\/v1\/workspaces$/)
    expect((init!.headers as Record<string, string>).Authorization).toBe('Bearer tok-123')
  })

  it('turns the backend error envelope into an ApiError', async () => {
    mockFetch(() => ({ status: 429, body: { error: { code: 'quota_exceeded', message: 'Daily AI limit reached.' } } }))
    await expect(api('/workspaces/x/chat', { method: 'POST', json: {} })).rejects.toMatchObject({ status: 429, code: 'quota_exceeded', message: 'Daily AI limit reached.' })
  })

  it('reports network failures (e.g. sleeping server) clearly', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    const err = (await api('/health').catch((e: unknown) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.code).toBe('network_error')
  })
})

describe('file validation', () => {
  it('accepts supported files and rejects others', () => {
    expect(validateFile(new File(['x'], 'notes.md'))).toBeNull()
    expect(validateFile(new File(['x'], 'virus.exe'))).toMatch(/only PDF/)
    expect(validateFile(new File([], 'empty.txt'))).toMatch(/empty/)
    const big = new File(['x'], 'big.pdf')
    Object.defineProperty(big, 'size', { value: 21 * 1024 * 1024 })
    expect(validateFile(big)).toMatch(/20 MB/)
  })
})

describe('Markdown', () => {
  it('renders citation chips and never injects HTML', async () => {
    const onCite = vi.fn()
    render(<Markdown text={'**Normalization** reduces redundancy [S1].\n- item <img src=x onerror=alert(1)>'} onCite={onCite} />)
    expect(screen.getByText('Normalization').tagName).toBe('STRONG')
    await userEvent.click(screen.getByRole('button', { name: 'Show source S1' }))
    expect(onCite).toHaveBeenCalledWith('S1')
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument()
  })
})

describe('components', () => {
  it('SourceCard shows file, page and relevance', () => {
    render(<SourceCard c={{ label: 'S2', chunk_id: 'c', document_id: 'd', filename: 'week3.pdf', page_number: 7, section_title: null, quote_text: 'TCP is reliable', score: 0.82 }} />)
    expect(screen.getByText('week3.pdf')).toBeInTheDocument()
    expect(screen.getByText(/Page 7/)).toBeInTheDocument()
    expect(screen.getByText(/82% match/)).toBeInTheDocument()
  })

  it('StatusBadge labels each document state', () => {
    const { rerender } = render(<StatusBadge status="PROCESSING" />)
    expect(screen.getByText('Processing')).toBeInTheDocument()
    rerender(<StatusBadge status="FAILED" />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })
})

describe('pages', () => {
  it('Workspaces page shows the empty state, then creates a workspace', async () => {
    const created = { id: 'w1', name: 'Computer Networks', description: '', document_count: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }
    let list: unknown[] = []
    mockFetch((url, init) => {
      if (init?.method === 'POST') { list = [created]; return { status: 201, body: created } }
      if (url.endsWith('/workspaces')) return { body: list }
      return { body: {} }
    })
    wrap(<WorkspacesPage />)
    expect(await screen.findByText('No workspaces yet')).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: /new workspace/i })[0])
    await userEvent.type(screen.getByLabelText('Course name'), 'Computer Networks')
    await userEvent.click(screen.getByRole('button', { name: 'Create workspace' }))
    expect(await screen.findByText('Computer Networks')).toBeInTheDocument()
  })

  it('Workspaces page surfaces API errors with a retry', async () => {
    mockFetch(() => ({ status: 500, body: { error: { code: 'internal_error', message: 'Something went wrong on our side.' } } }))
    wrap(<WorkspacesPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong on our side.')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('Login page shows Supabase auth errors', async () => {
    const { supabase } = await import('@/lib/supabase')
    vi.mocked(supabase.auth.getSession).mockResolvedValueOnce({ data: { session: null } } as never)
    wrap(<LoginPage />)
    await userEvent.type(await screen.findByLabelText('Email'), 'a@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrongpass')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid login credentials'))
  })
})
