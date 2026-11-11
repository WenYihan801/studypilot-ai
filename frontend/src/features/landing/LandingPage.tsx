import { BookOpenCheck, FileSearch, Layers, LineChart, MessageSquareQuote, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'
import { Logo } from '@/app/Logo'
import { useAuth } from '@/features/auth/AuthProvider'

const YEAR = new Date().getFullYear()

const FEATURES = [
  { icon: FileSearch, title: 'Upload your materials', text: 'PDF, DOCX, TXT and Markdown are parsed, chunked and indexed with page and section numbers.' },
  { icon: MessageSquareQuote, title: 'Answers with real sources', text: 'Every answer cites the exact document and page. If your notes don’t cover it, StudyPilot says so.' },
  { icon: BookOpenCheck, title: 'Quizzes from your notes', text: 'Multiple choice, true/false and short answer — auto-graded with explanations and source links.' },
  { icon: Layers, title: 'Flashcards that track mastery', text: 'Flip, mark as learning or mastered, and review what is still due.' },
  { icon: LineChart, title: 'Progress you can see', text: 'A dashboard of study sessions, quiz scores and flashcard mastery from your real activity.' },
  { icon: ShieldCheck, title: 'Private by default', text: 'Row-level security isolates every user’s data. Files live in a private bucket.' },
]

export function LandingPage() {
  const { session } = useAuth()
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-2 text-sm">
          {session ? (
            <Link to="/app" className="rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700">Open app</Link>
          ) : (
            <>
              <Link to="/login" className="rounded-lg px-3 py-2 font-medium text-slate-700 hover:bg-slate-100">Sign in</Link>
              <Link to="/register" className="rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700">Get started</Link>
            </>
          )}
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-4 pt-12 pb-20 text-center sm:px-6 sm:pt-20">
        <p className="mb-4 inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">Cloud-based AI Study & Research Assistant</p>
        <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          Study from <span className="text-brand-600">your own</span> course materials — with answers you can verify.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Upload lecture notes and papers. Ask questions, get cited answers, generate quizzes and flashcards, and track your progress.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link to={session ? '/app' : '/register'} className="rounded-lg bg-brand-600 px-5 py-3 text-sm font-medium text-white shadow-sm hover:bg-brand-700">Start studying free</Link>
          <a href="#features" className="rounded-lg border border-slate-300 px-5 py-3 text-sm font-medium text-slate-800 hover:bg-slate-50">See features</a>
        </div>
      </section>

      <section id="features" className="border-t border-slate-200 bg-slate-50 py-20">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 inline-flex rounded-lg bg-brand-50 p-2 text-brand-600"><Icon className="size-5" aria-hidden /></div>
              <h3 className="font-semibold text-slate-900">{title}</h3>
              <p className="mt-2 text-sm text-slate-600">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:px-6">
        <span>© {YEAR} StudyPilot AI — a student portfolio project.</span>
        <Link to="/privacy" className="hover:text-slate-700">Privacy & AI data use</Link>
      </footer>
    </div>
  )
}

export function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
      <Link to="/"><Logo /></Link>
      <h1 className="mt-8 text-2xl font-semibold">Privacy & AI data use</h1>
      <div className="mt-6 space-y-4 text-sm leading-relaxed text-slate-700">
        <p><strong>Third-party AI processing.</strong> Text extracted from your uploaded documents and your questions are sent to Google’s Gemini API to create embeddings, answers, summaries, quizzes and flashcards.</p>
        <p><strong>Free-tier terms differ.</strong> This deployment may use the Gemini API free tier. Google’s pricing page states that content sent on the free tier may be used to improve Google’s products; paid-tier content is not. Do not upload confidential, personal or sensitive documents.</p>
        <p><strong>Use public or self-made materials.</strong> For demos, use lecture notes you wrote yourself or openly licensed material.</p>
        <p><strong>Storage and isolation.</strong> Files are stored in a private Supabase Storage bucket. Database rows are protected by PostgreSQL Row Level Security so users can only access their own workspaces, documents, conversations, quizzes and flashcards.</p>
        <p><strong>Deletion.</strong> Deleting a document removes its file and all vectors. Deleting a workspace removes everything inside it. Deleting your account (Settings) removes all files, vectors and records, then your login.</p>
      </div>
    </div>
  )
}
