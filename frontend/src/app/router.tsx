/* oxlint-disable react/only-export-components -- route table, not a hot-reloaded component module */
import { lazy, Suspense, type ComponentType, type ReactNode } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'
import { Spinner } from '@/components/ui'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from '@/features/auth/AuthPages'
import { LandingPage, PrivacyPage } from '@/features/landing/LandingPage'
import { AppLayout } from './AppLayout'
import { NotFound } from './NotFound'

// Public pages load eagerly; everything behind login is code-split per feature.
function page<M extends Record<string, unknown>>(loader: () => Promise<M>, name: keyof M): ReactNode {
  const C = lazy(() => loader().then((m) => ({ default: m[name] as ComponentType })))
  return <Suspense fallback={<Spinner />}><C /></Suspense>
}

const ws = () => import('@/features/workspaces/WorkspaceLayout')
const quiz = () => import('@/features/quiz/QuizTakePage')
const cards = () => import('@/features/flashcards/FlashcardPages')

export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  { path: '/privacy', element: <PrivacyPage /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },
  {
    path: '/app',
    element: <AppLayout />,
    children: [
      { index: true, element: page(() => import('@/features/progress/DashboardPage'), 'DashboardPage') },
      { path: 'workspaces', element: page(() => import('@/features/workspaces/WorkspacesPage'), 'WorkspacesPage') },
      {
        path: 'workspaces/:workspaceId',
        element: page(ws, 'WorkspaceLayout'),
        children: [
          { index: true, element: page(() => import('@/features/documents/DocumentsPanel'), 'DocumentsPanel') },
          { path: 'chat', element: page(() => import('@/features/chat/ChatPage'), 'ChatPage') },
          { path: 'quizzes', element: page(() => import('@/features/quiz/QuizStudioPage'), 'QuizStudioPage') },
          { path: 'flashcards', element: page(cards, 'FlashcardsPage') },
        ],
      },
      { path: 'documents/:documentId/summary', element: page(() => import('@/features/documents/SummaryPage'), 'SummaryPage') },
      { path: 'quizzes/:quizId/take', element: page(quiz, 'QuizTakePage') },
      { path: 'quiz-attempts/:attemptId', element: page(quiz, 'QuizResultPage') },
      { path: 'flashcard-sets/:setId', element: page(cards, 'FlashcardReviewPage') },
      { path: 'progress', element: page(() => import('@/features/progress/ProgressPage'), 'ProgressPage') },
      { path: 'settings', element: page(() => import('@/features/settings/SettingsPage'), 'SettingsPage') },
      { path: '*', element: <NotFound /> },
    ],
  },
  { path: '*', element: <NotFound /> },
]

export const router = createBrowserRouter(routes)
