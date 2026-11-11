# Architecture

StudyPilot AI is a **modular monolith**: one React SPA, one FastAPI service, and managed cloud services.
No microservices, no queues, no Kubernetes — every moving part is something a single developer can run and debug.

## System diagram

```mermaid
flowchart LR
  subgraph Browser
    SPA["React + TypeScript SPA<br/>(Vercel)"]
  end
  subgraph Render["Render — FastAPI (Python 3.12)"]
    API["/api/v1 routes<br/>(thin: parse → service → schema)"]
    SVC["Services<br/>workspace · document · ingestion · retrieval · chat<br/>summary · quiz · flashcard · dashboard · usage"]
    REPO["Repositories<br/>(ownership filters built in)"]
    AIAD["AI Provider Adapter<br/>generate_text · generate_structured_output · embed_texts"]
  end
  subgraph Supabase
    AUTH["Auth (JWT, JWKS)"]
    PG[("PostgreSQL + pgvector<br/>RLS on every table")]
    ST[("Storage — private bucket")]
  end
  GEM["Gemini API"]

  SPA -- "sign up / sign in" --> AUTH
  SPA -- "HTTPS + Bearer JWT" --> API
  API --> SVC --> REPO
  REPO -- "user JWT → RLS enforced" --> PG
  REPO -- "secret key (integrity tables, background jobs)" --> PG
  SVC -- "secret key, path = user_id/…" --> ST
  SVC --> AIAD --> GEM
  API -. "verify JWT via JWKS" .-> AUTH
```

## Request lifecycle (example: chat)

```mermaid
sequenceDiagram
  participant U as Browser
  participant A as FastAPI
  participant DB as Postgres (RLS)
  participant G as Gemini
  U->>A: POST /workspaces/{id}/chat (Bearer JWT)
  A->>A: verify JWT (JWKS), rate limit, daily quota
  A->>DB: workspace belongs to user? (RLS + explicit user_id)
  A->>G: embed question (RETRIEVAL_QUERY, 768-d)
  A->>DB: match_chunks(workspace_id, user_id) — exact cosine search
  alt no chunk above min score
    A-->>U: "materials don't cover this" (no LLM call)
  else relevant chunks
    A->>G: grounded prompt with [S1..Sn] sources (JSON schema)
    A->>A: Pydantic validate · drop citations not in this retrieval · regenerate once if none valid
    A->>DB: save messages + citations, usage event, activity
    A-->>U: answer + source cards (file, page, quote, score)
  end
```

## Key design decisions

| Decision | Why | Trade-off |
|---|---|---|
| **Modular monolith** (FastAPI + services/repositories) | One deployable, easy to debug on an 8 GB laptop | Scales vertically only — fine for this workload |
| **Backend reads DB with the user's JWT** (`postgrest.auth(token)`) | RLS really protects data, not just "is enabled" | One Supabase client per request (cheap HTTP client) |
| **Secret key only for integrity tables + background ingestion** | Users must not be able to forge quiz scores or reset AI quota through the public PostgREST API | Those code paths must filter `user_id` explicitly — covered by tests |
| **JWT verification via JWKS (ES256/RS256)** | Supabase's current asymmetric signing keys; no shared secret on the server | First request fetches the key set (cached 1 h) |
| **Embeddings: `gemini-embedding-001`, 768 dimensions, L2-normalised** | Default 3072-d exceeds pgvector's 2,000-d index limit; 768 is an officially recommended size; truncated output must be normalised | Changing model/dimension requires re-embedding everything |
| **Exact (filtered) vector search, no HNSW yet** | Every query filters by workspace; HNSW applies filters *after* the graph search and can return too few rows | Linear scan per workspace — fast at study-material scale; add HNSW + iterative scan later |
| **Background ingestion with FastAPI `BackgroundTasks`** | No worker service needed (Render free tier has no free workers) | A restart can interrupt processing → status stays `PROCESSING`; user can **Reprocess** after 10 min |
| **Map-reduce summaries** | Long documents never go into one prompt | More calls per summary → result is cached in `document_summaries` |
| **Structured output + Pydantic re-validation + business validation** | Model output is never trusted (JSON shape, MCQ has 4 distinct options, answer ∈ options, sources exist) | Invalid questions are discarded, so a quiz can have fewer questions than requested |
| **Mock AI provider** | Develop and test without network or quota; deterministic tests | Mock answers are not realistic text |
| **Daily quota in the database, rate limit in memory** | Quota survives restarts; per-minute limit is cheap | In-memory limiter is per-instance (fine with one instance) |

## Backend layout

```
backend/app/
  main.py               app factory: CORS allowlist, error handlers, router
  api/deps.py           Ctx: current user, user-scoped DB, admin DB, storage, AI provider
  api/v1/routes.py      all endpoints (thin)
  core/                 config (env), security (JWKS), errors (envelope), rate_limit, logging (secret redaction)
  db/                   Gateway protocol + Supabase and in-memory implementations
  repositories/         TableRepo with owner filtering; one repo per table
  services/             business logic (no FastAPI imports except via Ctx)
  providers/            base (interface), gemini, mock
  parsers/              PDF (pypdf), DOCX (python-docx), Markdown, TXT + file-type detection
  schemas/              api.py (request/response), ai.py (LLM output schemas)
```

## Frontend layout

```
frontend/src/
  app/          router (code-split per feature), AppLayout (sidebar, mobile menu, "server waking" banner)
  components/   ui primitives (Button, Card, Dialog, states), Markdown (safe renderer with citation chips)
  features/     auth · landing · workspaces · documents · chat · quiz · flashcards · progress · settings
  hooks/        TanStack Query hooks for every endpoint (polling while documents process)
  lib/          api client (JWT, error envelope, timeouts), supabase client, utils
  types/        API types mirroring backend schemas
```
