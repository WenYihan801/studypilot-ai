# Deployment Guide (Supabase → Render → Vercel)

**Current production (2026-11-11):** frontend https://studypilot-ai.vercel.app · API https://studypilot-api-j3bk.onrender.com · Supabase project `spylebeazwasxpzxuvif` (Singapore).

> **Check the official terms before you deploy — free plans change.** As of Nov 2026: Supabase free projects pause after
> 7 days of inactivity (max 2 active free projects, 500 MB database, 1 GB storage); Render free web services spin down after
> 15 minutes without traffic and take up to ~1 minute to wake (750 free instance hours/month per workspace); Vercel Hobby
> is for personal, non-commercial use; Gemini free-tier limits are per Google Cloud project, reset at midnight Pacific time,
> and free-tier content may be used to improve Google's products.

Recommended setup: **two Supabase projects** (`studypilot-dev` and `studypilot-prod`) — exactly the free limit — and two
Gemini API keys in two different Google Cloud projects so development does not use up the production quota.

---

## 0. Local tools (macOS, Apple silicon)

```bash
# Homebrew: https://brew.sh
brew install git uv supabase/tap/supabase
brew install fnm && fnm install --lts && fnm use --lts   # Node LTS (or use nvm)
uv python install 3.12
```

No Docker, no local PostgreSQL and no local models are needed.

## 1. Supabase

1. **Create a project** at <https://supabase.com/dashboard> → *New project*. Choose a region near your users
   (e.g. Southeast Asia (Singapore)) and save the database password in a password manager.
2. **API keys** — *Project Settings → API Keys*:
   * `Publishable key` (`sb_publishable_…`) → frontend `VITE_SUPABASE_PUBLISHABLE_KEY` and backend `SUPABASE_PUBLISHABLE_KEY`.
   * `Secret key` (`sb_secret_…`) → **backend only** `SUPABASE_SECRET_KEY`. Never put it in the frontend or in Git.
   * Project URL (`https://<ref>.supabase.co`) → `SUPABASE_URL` / `VITE_SUPABASE_URL`.
3. **JWT signing keys** — *Project Settings → JWT Keys*. The backend verifies tokens with the public JWKS and only accepts
   ES256/RS256. If the page shows the project still signs with the *Legacy JWT secret* (HS256), click **Migrate**, create an
   asymmetric key (ECC P-256 recommended) and **Rotate keys** so it becomes the current key. Verify:
   `curl https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` must return at least one key.
4. **Apply the schema** from your laptop:
   ```bash
   cd studypilot-ai
   supabase login
   supabase link --project-ref <your-project-ref>
   supabase db push            # applies supabase/migrations/*.sql (no Docker needed)
   ```
   Check in *Table Editor* that the tables exist, *Storage* shows a **private** `documents` bucket, and *Authentication →
   Policies* shows RLS enabled on every table.
5. **Auth URLs** — *Authentication → URL Configuration*:
   * Site URL: `http://localhost:5173` for dev; your Vercel URL for prod.
   * Redirect URLs: add `http://localhost:5173/**` and `https://<your-app>.vercel.app/**`
     (needed for email confirmation and `/reset-password`).
6. **Email** — Supabase's built-in email sender is rate-limited and meant for testing. For a public demo, either configure custom
   SMTP (*Authentication → Emails → SMTP Settings*) or disable "Confirm email" for the demo project.
7. **Verify RLS on the real project** (recommended):
   create two users in *Authentication → Users → Add user* (tick auto-confirm), then
   ```bash
   cd backend
   RLS_SUPABASE_URL=… RLS_PUBLISHABLE_KEY=… RLS_USER_A_EMAIL=… RLS_USER_A_PASSWORD=… \
   RLS_USER_B_EMAIL=… RLS_USER_B_PASSWORD=… uv run pytest tests/integration -v
   ```

## 2. Gemini API key

1. <https://aistudio.google.com/apikey> → *Create API key* (one per Google Cloud project: dev and prod).
2. Check current limits for your project at <https://aistudio.google.com/rate-limit>.
3. Model IDs are environment variables (`GEMINI_CHAT_MODEL`, `GEMINI_QUIZ_MODEL`, `GEMINI_EMBEDDING_MODEL`). Before deploying,
   confirm they are still listed (not deprecated) on <https://ai.google.dev/gemini-api/docs/pricing>.
   **Do not change `GEMINI_EMBEDDING_MODEL` or `EMBEDDING_DIM` after documents exist** — embeddings from different models are
   incompatible; you would need to re-process every document.

## 3. Backend on Render

1. Push the repository to GitHub (the `main` branch).
2. Render Dashboard → **New → Blueprint** → select the repo. Render reads `render.yaml`
   (service `studypilot-api`, root `backend`, `uv sync --frozen --no-dev`, health check `/api/v1/health`).
3. Fill in the secret environment variables Render asks for:
   `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`, and `CORS_ORIGINS`
   (temporarily `http://localhost:5173`; you will add the Vercel URL in step 4.4).
4. Deploy, then check `https://studypilot-api.onrender.com/api/v1/health` →
   `{"status":"ok", "environment":"production", "ai_provider":"gemini"}` and open `/docs`.

Free-instance notes: the filesystem is ephemeral (the app never stores files locally); a restart during document
processing leaves the document in `PROCESSING` — after 10 minutes the user can click **Reprocess**.

## 4. Frontend on Vercel

1. <https://vercel.com/new> → import the repo → **Root Directory: `frontend`** (framework preset: Vite).
2. Environment variables (Production and Preview):
   `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_API_BASE_URL=https://studypilot-api.onrender.com`.
3. Deploy. `vercel.json` rewrites all paths to `index.html` (deep links work) and adds basic security headers.
4. Back in Render, set `CORS_ORIGINS=https://<your-app>.vercel.app` (comma-separate to keep localhost) and redeploy.
5. In Supabase *URL Configuration*, set Site URL to the Vercel URL.

## 5. Production smoke test (do this before every demo)

- [ ] `GET /api/v1/health` OK (wakes the Render instance)
- [ ] Register → confirm email → sign in → sign out → password reset email arrives
- [ ] Create workspace, upload `sample_data/*.md` and a PDF → all reach **Ready**
- [ ] Chat question returns source cards with file + page; an off-topic question says the materials are insufficient
- [ ] Generate & submit a quiz; generate flashcards and mark one mastered
- [ ] Dashboard numbers change; Settings shows AI usage
- [ ] Second account cannot see the first account's workspace URL (404)
- [ ] `E2E_BASE_URL=https://<your-app>.vercel.app E2E_EMAIL=… E2E_PASSWORD=… npx playwright test` passes
- [ ] Supabase *Reports*: database and storage usage well below free limits

## 6. Logs and quotas

* Render → service → *Logs* (secrets are redacted by the app's logging filter).
* Supabase → *Logs & Analytics* and *Reports* (DB size, storage, auth).
* Google AI Studio → *Usage* / *Rate limit* for the Gemini project.
* In the app: *Learning progress → AI usage* and *Settings → AI usage & limits*.

When the Gemini free quota runs out, the API returns a clear `ai_rate_limited` error. For development, switch the backend
to `AI_PROVIDER=mock` and keep working.
