import { supabase } from './supabase'

export const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

// --- "server is waking up" signal (Render free instances sleep after 15 min idle) -------------
type Listener = (waking: boolean) => void
const listeners = new Set<Listener>()
let pending = 0
let wakingTimer: ReturnType<typeof setTimeout> | null = null

export function onServerWaking(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
function emit(waking: boolean) {
  listeners.forEach((l) => l(waking))
}
function begin() {
  pending += 1
  if (!wakingTimer) wakingTimer = setTimeout(() => emit(true), 5000)
}
function end() {
  pending = Math.max(0, pending - 1)
  if (pending === 0) {
    if (wakingTimer) clearTimeout(wakingTimer)
    wakingTimer = null
    emit(false)
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown; timeoutMs?: number } = {}): Promise<T> {
  const { json, timeoutMs = 120_000, ...rest } = init
  const headers: Record<string, string> = { ...(await authHeader()), ...(rest.headers as Record<string, string>) }
  if (json !== undefined) headers['Content-Type'] = 'application/json'
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  begin()
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/v1${path}`, {
      ...rest,
      headers,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      signal: controller.signal,
    })
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === 'AbortError'
    throw new ApiError(0, aborted ? 'timeout' : 'network_error',
      aborted ? 'The request timed out. Please try again.' : 'Cannot reach the server. It may be starting up — try again in a minute.')
  } finally {
    clearTimeout(timeout)
    end()
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const e = body?.error
    if (res.status === 401) await supabase.auth.signOut().catch(() => undefined)
    throw new ApiError(res.status, e?.code ?? 'http_error', e?.message ?? `Request failed (${res.status})`)
  }
  return body as T
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return 'Something went wrong.'
}
