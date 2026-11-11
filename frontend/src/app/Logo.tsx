export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight text-slate-900">
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#4f46e5" />
        <path d="M9 21l7-12 7 12h-4.5L16 16.5 13.5 21z" fill="#fff" />
      </svg>
      {!compact && <span>StudyPilot <span className="text-brand-600">AI</span></span>}
    </span>
  )
}
