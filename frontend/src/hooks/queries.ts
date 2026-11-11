import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  Attempt, AttemptResult, ChatResponse, Conversation, ConversationSummary, Dashboard, Difficulty, DocumentItem,
  Flashcard, FlashcardSet, FlashcardSetListItem, Mastery, Profile, QuestionType, Quiz, QuizListItem, Review,
  SummaryResponse, Usage, Workspace,
} from '@/types/api'

export const keys = {
  workspaces: ['workspaces'] as const,
  workspace: (id: string) => ['workspace', id] as const,
  documents: (wid: string) => ['documents', wid] as const,
  document: (id: string) => ['document', id] as const,
  summary: (id: string) => ['summary', id] as const,
  conversations: (wid: string) => ['conversations', wid] as const,
  conversation: (id: string) => ['conversation', id] as const,
  quizzes: (wid: string) => ['quizzes', wid] as const,
  quiz: (id: string) => ['quiz', id] as const,
  attempt: (id: string) => ['attempt', id] as const,
  flashSets: (wid: string) => ['flashSets', wid] as const,
  flashSet: (id: string) => ['flashSet', id] as const,
  due: (wid?: string) => ['due', wid ?? 'all'] as const,
  reviews: (id: string) => ['reviews', id] as const,
  dashboard: ['dashboard'] as const,
  usage: ['usage'] as const,
  me: ['me'] as const,
}

// ---------------------------------------------------------------- workspaces
export const useWorkspaces = () => useQuery({ queryKey: keys.workspaces, queryFn: () => api<Workspace[]>('/workspaces') })
export const useWorkspace = (id: string) => useQuery({ queryKey: keys.workspace(id), queryFn: () => api<Workspace>(`/workspaces/${id}`) })

export function useSaveWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id?: string; name: string; description: string }) =>
      id ? api<Workspace>(`/workspaces/${id}`, { method: 'PATCH', json: body }) : api<Workspace>('/workspaces', { method: 'POST', json: body }),
    onSuccess: (ws) => {
      qc.invalidateQueries({ queryKey: keys.workspaces })
      qc.setQueryData(keys.workspace(ws.id), ws)
      qc.invalidateQueries({ queryKey: keys.dashboard })
    },
  })
}

export function useDeleteWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`/workspaces/${id}`, { method: 'DELETE' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: keys.workspaces }); qc.invalidateQueries({ queryKey: keys.dashboard }) },
  })
}

// ---------------------------------------------------------------- documents
export function useDocuments(wid: string) {
  return useQuery({
    queryKey: keys.documents(wid),
    queryFn: () => api<DocumentItem[]>(`/workspaces/${wid}/documents`),
    // Poll while anything is still being processed in the background.
    refetchInterval: (q) => (q.state.data?.some((d) => d.status === 'UPLOADED' || d.status === 'PROCESSING') ? 2500 : false),
  })
}
export const useDocument = (id: string) => useQuery({ queryKey: keys.document(id), queryFn: () => api<DocumentItem>(`/documents/${id}`) })

export function useUploadDocument(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api<DocumentItem>(`/workspaces/${wid}/documents`, { method: 'POST', body: form, timeoutMs: 180_000 })
    },
    onSettled: () => { qc.invalidateQueries({ queryKey: keys.documents(wid) }); qc.invalidateQueries({ queryKey: keys.workspaces }) },
  })
}

export function useDocumentAction(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: 'delete' | 'process' }): Promise<void> => {
      if (action === 'delete') await api<void>(`/documents/${id}`, { method: 'DELETE' })
      else await api<DocumentItem>(`/documents/${id}/process`, { method: 'POST' })
    },
    onSettled: () => { qc.invalidateQueries({ queryKey: keys.documents(wid) }); qc.invalidateQueries({ queryKey: keys.workspaces }) },
  })
}

export const useCachedSummary = (id: string) =>
  useQuery({ queryKey: keys.summary(id), queryFn: () => api<SummaryResponse | null>(`/documents/${id}/summary`) })

export function useGenerateSummary(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (force: boolean) => api<SummaryResponse>(`/documents/${id}/summary`, { method: 'POST', json: { force }, timeoutMs: 240_000 }),
    onSuccess: (data) => { qc.setQueryData(keys.summary(id), data); qc.invalidateQueries({ queryKey: keys.usage }) },
  })
}

// ---------------------------------------------------------------- chat
export const useConversations = (wid: string) =>
  useQuery({ queryKey: keys.conversations(wid), queryFn: () => api<ConversationSummary[]>(`/workspaces/${wid}/conversations`) })
export const useConversation = (id: string | null) =>
  useQuery({ queryKey: keys.conversation(id ?? ''), queryFn: () => api<Conversation>(`/conversations/${id}`), enabled: Boolean(id) })

export function useAsk(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { question: string; conversation_id?: string | null; document_ids?: string[] }) =>
      api<ChatResponse>(`/workspaces/${wid}/chat`, { method: 'POST', json: body }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: keys.conversations(wid) })
      qc.invalidateQueries({ queryKey: keys.conversation(res.conversation_id) })
    },
  })
}

export function useDeleteConversation(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`/conversations/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.conversations(wid) }),
  })
}

// ---------------------------------------------------------------- quizzes
export const useQuizzes = (wid: string) => useQuery({ queryKey: keys.quizzes(wid), queryFn: () => api<QuizListItem[]>(`/workspaces/${wid}/quizzes`) })
export const useQuiz = (id: string) => useQuery({ queryKey: keys.quiz(id), queryFn: () => api<Quiz>(`/quizzes/${id}`) })
export const useAttemptResult = (id: string) => useQuery({ queryKey: keys.attempt(id), queryFn: () => api<AttemptResult>(`/quiz-attempts/${id}`) })

export function useGenerateQuiz(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { title?: string; num_questions: number; difficulty: Difficulty; types: QuestionType[]; document_ids?: string[] }) =>
      api<Quiz>(`/workspaces/${wid}/quizzes/generate`, { method: 'POST', json: body, timeoutMs: 240_000 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.quizzes(wid) }),
  })
}

export function useDeleteQuiz(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`/quizzes/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.quizzes(wid) }),
  })
}

export const useStartAttempt = () => useMutation({ mutationFn: (quizSetId: string) => api<Attempt>('/quiz-attempts', { method: 'POST', json: { quiz_set_id: quizSetId } }) })

export function useSubmitAttempt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, answers }: { id: string; answers: Record<string, string> }) =>
      api<AttemptResult>(`/quiz-attempts/${id}/submit`, { method: 'POST', json: { answers }, timeoutMs: 120_000 }),
    onSuccess: (res) => {
      qc.setQueryData(keys.attempt(res.attempt.id), res)
      qc.invalidateQueries({ queryKey: keys.dashboard })
      if (res.quiz.workspace_id) qc.invalidateQueries({ queryKey: keys.quizzes(res.quiz.workspace_id) })
    },
  })
}

// ---------------------------------------------------------------- flashcards
export const useFlashSets = (wid: string) => useQuery({ queryKey: keys.flashSets(wid), queryFn: () => api<FlashcardSetListItem[]>(`/workspaces/${wid}/flashcard-sets`) })
export const useFlashSet = (id: string) => useQuery({ queryKey: keys.flashSet(id), queryFn: () => api<FlashcardSet>(`/flashcard-sets/${id}`) })
export const useDue = (wid?: string) => useQuery({ queryKey: keys.due(wid), queryFn: () => api<Flashcard[]>(`/flashcards/due${wid ? `?workspace_id=${wid}` : ''}`) })
export const useReviews = (id: string | null) => useQuery({ queryKey: keys.reviews(id ?? ''), queryFn: () => api<Review[]>(`/flashcards/${id}/reviews`), enabled: Boolean(id) })

export function useGenerateFlashcards(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { title?: string; count: number; document_ids?: string[] }) =>
      api<FlashcardSet>(`/workspaces/${wid}/flashcards/generate`, { method: 'POST', json: body, timeoutMs: 240_000 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.flashSets(wid) }),
  })
}

export function useDeleteFlashSet(wid: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`/flashcard-sets/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.flashSets(wid) }),
  })
}

export function useUpdateMastery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: Mastery }) => api<Flashcard>(`/flashcards/${id}`, { method: 'PATCH', json: { mastery_status: status } }),
    onSuccess: (card) => {
      qc.setQueryData<FlashcardSet>(keys.flashSet(card.set_id), (old) => old && { ...old, cards: old.cards.map((c) => (c.id === card.id ? card : c)) })
      qc.invalidateQueries({ queryKey: ['due'] })
      qc.invalidateQueries({ queryKey: keys.reviews(card.id) })
      qc.invalidateQueries({ queryKey: keys.flashSets(card.workspace_id) })
      qc.invalidateQueries({ queryKey: keys.dashboard })
    },
  })
}

// ---------------------------------------------------------------- dashboard / account
export const useDashboard = () => useQuery({ queryKey: keys.dashboard, queryFn: () => api<Dashboard>('/dashboard/summary') })
export const useUsage = () => useQuery({ queryKey: keys.usage, queryFn: () => api<Usage>('/usage') })
export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api<Profile>('/me') })

export function useUpdateMe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (display_name: string) => api<Profile>('/me', { method: 'PATCH', json: { display_name } }),
    onSuccess: (p) => qc.setQueryData(keys.me, p),
  })
}

export const useDeleteAccount = () => useMutation({ mutationFn: () => api<void>('/me', { method: 'DELETE' }) })
