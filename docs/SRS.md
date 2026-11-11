# Software Requirements Specification — StudyPilot AI v1.0

## 1. Purpose and scope

StudyPilot AI (Cloud-based AI Study & Research Assistant) lets university students, postgraduates and self-learners upload
course materials and study from them with an AI that **answers only from those materials and shows its sources**.
V1.0 is a web application (desktop and mobile browsers) deployed on Vercel (frontend), Render (API) and Supabase
(database, auth, storage), using the Gemini API for all AI inference.

Out of scope for V1.0: OCR for scanned PDFs, spaced-repetition scheduling algorithms, collaboration/sharing, payments,
local or self-hosted models, mobile apps.

## 2. Users

| Persona | Goal |
|---|---|
| Undergraduate | Revise lecture notes, check understanding before exams |
| Postgraduate / researcher | Query papers and get answers traceable to page numbers |
| Self-learner | Turn notes into quizzes and flashcards |

## 3. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Register, sign in, sign out, persistent session, password reset, profile (display name) | Done |
| FR-2 | Users can only access their own data (workspaces, documents, chats, quizzes, cards, progress) | Done (RLS + service checks, tested) |
| FR-3 | Create / edit / delete workspaces; delete removes all related rows, vectors and files | Done |
| FR-4 | Upload PDF, DOCX, TXT, Markdown ≤ 20 MB; validate extension, MIME and file signature; reject executables and duplicates; store privately | Done |
| FR-5 | Automatic processing: extract text (pages/sections), chunk, embed, store vectors; show status UPLOADED/PROCESSING/READY/FAILED with failure reason; reprocess | Done |
| FR-6 | Document summary with 8 sections (overview, topics, concepts, definitions, arguments, takeaways, checklist, references); long documents summarised in parts; cached | Done |
| FR-7 | RAG chat scoped to user + workspace; answers show document, page, quoted text and relevance; says when materials are insufficient; never shows a citation that was not retrieved | Done |
| FR-8 | Quiz generation (MCQ, true/false, short answer; count, difficulty, documents); Pydantic + rule validation before saving; auto-grading; results with explanations and source passages; scores saved | Done |
| FR-9 | Flashcards: generate, flip, mark LEARNING/MASTERED, list cards to review, review history | Done |
| FR-10 | Dashboard: workspaces, documents, study sessions, quizzes, average score, cards to review, recent activity, progress charts — all from the database | Done |
| FR-11 | AI usage accounting (calls, tokens, estimated cost) and per-user daily limit | Done |
| FR-12 | Account deletion removes files, vectors, rows and the auth user | Done |

## 4. Non-functional requirements

| ID | Requirement | How it is met |
|---|---|---|
| NFR-1 Security | HTTPS, JWT verification, RLS, CORS allowlist, private storage, no secrets in the browser, secrets redacted from logs | See `privacy.md`, `database.md` |
| NFR-2 Cost control | Daily quota, rate limits, input/output caps, quiz/card caps, no duplicate embeddings, summary cache, bounded retries (max 3 attempts), Mock provider | `services/usage.py`, `providers/gemini.py` |
| NFR-3 Reliability | No document can stay stuck in PROCESSING after an error; reprocessing is idempotent; cold-start UX | `IngestionService`, "waking up" banner |
| NFR-4 Maintainability | Modular monolith, service/repository layers, provider adapter, typed schemas, lint + tests in CI | `architecture.md` |
| NFR-5 Usability | Responsive (mobile menu), loading/empty/error/success states on every page, keyboard-accessible controls | Frontend |
| NFR-6 Portability | Model IDs and limits in environment variables; AI provider swappable | `core/config.py` |
| NFR-7 Dev hardware | Runs on an 8 GB Apple-silicon MacBook: no Docker, no local DB, no local models | `README.md` |

## 5. Constraints and assumptions

* Free tiers change: Gemini free-tier limits are per project and reset at midnight Pacific; free-tier content may be used by Google
  to improve products. Supabase free projects pause after 7 days of inactivity. Render free services sleep after 15 minutes idle.
  Vercel Hobby is for non-commercial use. Re-check before each deployment.
* Users upload public or self-made materials (see `privacy.md`).
