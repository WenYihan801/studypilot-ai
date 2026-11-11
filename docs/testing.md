# Testing & Test Report

All numbers below were produced by actually running the suites on 2026-11-11 (Linux, Python 3.12, Node 22).
Nothing is estimated. Re-run them yourself with the commands shown.

## Summary

| Suite | Tool | Command | Result |
|---|---|---|---|
| Backend unit + API | Pytest, HTTPX (TestClient) | `cd backend && uv run pytest -q` | **76 passed**, 7 skipped (live-Supabase tests, need credentials) |
| Database schema + RLS | PostgreSQL 16 + pgvector 0.6.0, psql | see `supabase/tests/README.md` | Migration applied cleanly; all isolation checks behaved as expected (below) |
| Frontend unit + component | Vitest, React Testing Library | `cd frontend && npm test` | **10 passed** |
| E2E smoke (public pages) | Playwright (desktop + Pixel 7) | `npx playwright test e2e/smoke.spec.ts` | **8 passed** |
| E2E full user journey | Playwright | `E2E_EMAIL=… E2E_PASSWORD=… npx playwright test e2e/full-flow.spec.ts` | Not yet run: requires your deployed stack + a test account |
| Live RLS against Supabase | Pytest + supabase-py | `uv run pytest tests/integration -v` (env vars in file header) | Not yet run: requires your Supabase project |
| RAG evaluation (26 questions) | `backend/eval/run_eval.py` | `AI_PROVIDER=gemini GEMINI_API_KEY=… uv run python -m eval.run_eval` | Not yet run with Gemini (see below) |

Lint/type checks: `ruff check` (backend) and `oxlint` + `tsc -b` (frontend) pass with zero findings.

## Coverage of the required test areas

| # | Area | Where |
|---|---|---|
| 1 | Registration & login | JWT verification (valid ES256, expired, wrong audience, wrong issuer, wrong key, HS256 forgery) in `test_api_core.py`; login error UI in `frontend.test.tsx`; full sign-in in `full-flow.spec.ts` |
| 2 | User data isolation | Cross-user 404s for workspaces, documents, uploads, chats, conversations, quizzes, attempts, flashcards, dashboard; retrieval scoped to workspace and user; SQL RLS check; live RLS tests |
| 3 | Workspace CRUD | `test_workspace_crud`, validation, frontend create flow |
| 4 | File upload | PDF/DOCX/TXT/MD success; unsupported type; executable disguised as `.txt`; extension/MIME/content mismatch; size limit; duplicate (409); daily upload limit |
| 5 | File parsing | PDF page numbers; DOCX headings → sections; Markdown headings (ignoring code blocks); scanned PDF → FAILED with OCR message |
| 6 | Chunking | size/overlap bounds, index order, overlap continuity, no page crossing |
| 7 | Embedding generation | 768-d vectors stored per chunk; Gemini adapter normalisation; dimension-mismatch rejection; embedding reuse for identical files (no new API calls) |
| 8 | Vector retrieval | relevant chunk ranked first; document filter; workspace/user scoping |
| 9 | RAG Q&A | grounded answer with citations; no documents → insufficient **without** calling the LLM; unrelated question → insufficient; chat history saved/reloaded; prompt marks sources as untrusted |
| 10 | Citation validation | hallucinated `[S99]` removed and answer refused; unit test of `validate_citations` |
| 11 | Summaries | 8-section structure + references; cache hit makes no AI call; force regenerate; long document summarised in multiple parts, each prompt < 20k chars; not-ready document rejected |
| 12 | Quiz generation | answers hidden before submission; every question has source chunks; rule validation (4 distinct options, answer ∈ options, valid source, allowed type); count limit |
| 13 | Quiz grading | 3/4 → 75 %; short-answer LLM grading; double submit → 409; results include explanations + sources; best score in list |
| 14 | Flashcards | generation with sources; status changes; review history order; due list; set progress; invalid status 422 |
| 15 | Learning records | dashboard counts, averages, 14-day activity, mastery distribution from real rows; empty state for new users |
| 16 | AI usage limits | usage events recorded; daily quota → 429 while non-AI endpoints still work; per-minute AI rate limit; Gemini retries bounded to 3 attempts |
| 17 | Deletion & cleanup | document delete removes file + vectors; workspace delete removes all child rows and files; account delete removes everything but leaves other users intact |

Also covered: CORS allowlist, error envelope for unknown routes, secret redaction in logs, safe Markdown rendering (no HTML injection),
API client error handling and cold-start network errors.

## Database RLS check output (PostgreSQL 16 + pgvector, Supabase auth/storage stubbed)

```
profiles auto-created: 2
B sees A workspaces: 0
ERROR:  new row violates row-level security policy "documents_parent_owned" for table "documents"
ERROR:  new row violates row-level security policy for table "ai_usage_events"
ERROR:  new row violates row-level security policy for table "workspaces"
A sees own workspace name: A ws          (B's UPDATE silently affected 0 rows)
A match_chunks rows: 1
B match_chunks on A ws: 0
chunks after workspace delete (cascade): 0
```

## RAG evaluation

`backend/eval/questions.json` holds **26 fixed questions** over `sample_data/`: 20 answerable (each with the expected source file
and key terms) and 6 deliberately out of scope. The script runs the real upload → ingestion → chat path and reports:

* **source_hit_rate** — expected file among the citations
* **keyword_coverage** — key terms present in the answer (a rough faithfulness proxy; read the answers too)
* **answered_when_in_scope** — not wrongly refusing
* **correct_refusal_rate** — out-of-scope questions flagged as insufficient
* **invalid_citations** — always 0 by construction (unretrieved citations are removed)

Status: the pipeline was verified end-to-end with the **mock** provider only. Mock numbers measure nothing about answer quality,
so they are deliberately not reported here. Run it with your Gemini key (about 30 embedding calls + 26 chat calls; the
script waits 4 s between questions to stay under free-tier per-minute limits) and paste the generated
`eval/results/<timestamp>-gemini.md` table into this section. Use it to tune `RETRIEVAL_MIN_SCORE`, `RETRIEVAL_TOP_K`
and chunk size — change one parameter at a time and keep each result file.

## Known gaps

* No OCR — image-only PDFs fail with a clear message.
* `match_chunks` uses exact search; add HNSW when a workspace exceeds tens of thousands of chunks.
* The in-memory rate limiter is per instance (fine for a single Render instance).
* Quiz quality depends on the model; invalid questions are dropped, so a quiz may contain fewer questions than requested.
