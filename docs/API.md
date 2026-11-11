# API Documentation

Base URL: `https://<your-render-service>.onrender.com/api/v1` (local: `http://localhost:8000/api/v1`).
Interactive docs (Swagger UI) are served by the backend at `/docs`; the machine-readable spec is [`openapi.json`](openapi.json)
(generated from the code, so it cannot drift from the implementation).

## Authentication

Every endpoint except `GET /health` requires `Authorization: Bearer <Supabase access token>`.
The browser obtains the token from Supabase Auth (`supabase.auth.getSession()`); the backend verifies the
signature locally against the project's JWKS (`/auth/v1/.well-known/jwks.json`, ES256/RS256), plus `exp`, `aud=authenticated`
and `iss`. HS256 tokens are rejected.

## Authorization

Every resource is owned by a user. Services always filter by the caller's `user_id`; database reads use the caller's JWT,
so PostgreSQL RLS enforces the same rule a second time. A resource owned by someone else returns **404** (not 403),
so IDs cannot be probed for existence.

## Errors

All errors share one envelope:

```json
{ "error": { "code": "quota_exceeded", "message": "Daily AI limit of 100 requests reached. It resets at 00:00 UTC." } }
```

| HTTP | `code` examples | Meaning |
|---|---|---|
| 401 | `unauthorized`, `token_expired` | Missing/invalid/expired JWT |
| 404 | `not_found` | Does not exist **or** belongs to another user |
| 409 | `duplicate_file`, `already_processing`, `already_submitted` | State conflict |
| 422 | `validation_failed`, `unsupported_type`, `mime_mismatch`, `executable_rejected`, `file_too_large`, `no_ready_documents`, `document_not_ready`, `upload_limit` | Invalid input (Pydantic or business rule) |
| 429 | `quota_exceeded`, `rate_limited` | Daily AI quota or per-minute rate limit |
| 502/503 | `ai_provider_error`, `ai_invalid_output`, `ai_rate_limited` | The AI provider failed or returned unusable output (after bounded retries) |
| 500 | `internal_error` | Unexpected; details are logged server-side only |

## Validation & limits (defaults, configurable via env)

| Limit | Default |
|---|---|
| Upload size | 20 MB; extension **and** declared MIME **and** magic bytes must agree; executables rejected |
| Duplicate upload | same SHA-256 in the same workspace → 409 |
| Question length | 2,000 chars |
| Quiz questions | 1–20 per quiz |
| Flashcards | 1–30 per set |
| Daily AI requests | 100 per user (UTC day), stored in `ai_usage_events` |
| Rate limit | 60 req/min per user overall, 10 req/min for AI endpoints |

## Endpoints

| Method | Path | Auth | Request body | Success response | Error codes | Summary |
|---|---|---|---|---|---|---|
| `GET` | `/api/v1/health` | public | — | 200 HealthOut |  | Health |
| `GET` | `/api/v1/me` | JWT | — | 200 ProfileOut | 401, 404, 422 | Get Me |
| `DELETE` | `/api/v1/me` | JWT | — | 204  | 401, 404, 422 | Delete Me |
| `PATCH` | `/api/v1/me` | JWT | ProfileUpdate | 200 ProfileOut | 401, 404, 422 | Update Me |
| `GET` | `/api/v1/workspaces` | JWT | — | 200 list[WorkspaceOut] | 401, 404, 422 | List Workspaces |
| `POST` | `/api/v1/workspaces` | JWT | WorkspaceCreate | 201 WorkspaceOut | 401, 404, 422 | Create Workspace |
| `GET` | `/api/v1/workspaces/{workspace_id}` | JWT | — | 200 WorkspaceOut | 401, 404, 422 | Get Workspace |
| `PATCH` | `/api/v1/workspaces/{workspace_id}` | JWT | WorkspaceUpdate | 200 WorkspaceOut | 401, 404, 422 | Update Workspace |
| `DELETE` | `/api/v1/workspaces/{workspace_id}` | JWT | — | 204  | 401, 404, 422 | Delete Workspace |
| `GET` | `/api/v1/workspaces/{workspace_id}/documents` | JWT | — | 200 list[DocumentOut] | 401, 404, 422 | List Documents |
| `POST` | `/api/v1/workspaces/{workspace_id}/documents` | JWT | Body_upload_document_api_v1_workspaces__workspace_id__documents_post | 201 DocumentOut | 401, 404, 422, 409 | Upload Document |
| `GET` | `/api/v1/documents/{document_id}` | JWT | — | 200 DocumentOut | 401, 404, 422 | Get Document |
| `DELETE` | `/api/v1/documents/{document_id}` | JWT | — | 204  | 401, 404, 422 | Delete Document |
| `POST` | `/api/v1/documents/{document_id}/process` | JWT | — | 202 DocumentOut | 401, 404, 422, 409 | Reprocess Document |
| `GET` | `/api/v1/documents/{document_id}/summary` | JWT | — | 200 SummaryOut \| null | 401, 404, 422 | Get Summary |
| `POST` | `/api/v1/documents/{document_id}/summary` | JWT | application/json | 200 SummaryOut | 401, 404, 422, 429, 502 | Create Summary |
| `POST` | `/api/v1/workspaces/{workspace_id}/chat` | JWT | ChatRequest | 200 ChatResponse | 401, 404, 422, 429, 502 | Chat |
| `GET` | `/api/v1/workspaces/{workspace_id}/conversations` | JWT | — | 200 list[ConversationSummaryOut] | 401, 404, 422 | List Conversations |
| `GET` | `/api/v1/conversations/{conversation_id}` | JWT | — | 200 ConversationOut | 401, 404, 422 | Get Conversation |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | JWT | — | 204  | 401, 404, 422 | Delete Conversation |
| `POST` | `/api/v1/workspaces/{workspace_id}/quizzes/generate` | JWT | QuizGenerateRequest | 201 QuizOut | 401, 404, 422, 429, 502 | Generate Quiz |
| `GET` | `/api/v1/workspaces/{workspace_id}/quizzes` | JWT | — | 200 list[QuizListItem] | 401, 404, 422 | List Quizzes |
| `GET` | `/api/v1/quizzes/{quiz_set_id}` | JWT | — | 200 QuizOut | 401, 404, 422 | Get Quiz |
| `DELETE` | `/api/v1/quizzes/{quiz_set_id}` | JWT | — | 204  | 401, 404, 422 | Delete Quiz |
| `POST` | `/api/v1/quiz-attempts` | JWT | AttemptCreate | 201 AttemptOut | 401, 404, 422 | Start Attempt |
| `POST` | `/api/v1/quiz-attempts/{attempt_id}/submit` | JWT | AttemptSubmit | 200 AttemptResultOut | 401, 404, 422, 429, 502, 409 | Submit Attempt |
| `GET` | `/api/v1/quiz-attempts/{attempt_id}` | JWT | — | 200 AttemptResultOut | 401, 404, 422 | Get Attempt |
| `POST` | `/api/v1/workspaces/{workspace_id}/flashcards/generate` | JWT | FlashcardGenerateRequest | 201 FlashcardSetOut | 401, 404, 422, 429, 502 | Generate Flashcards |
| `GET` | `/api/v1/workspaces/{workspace_id}/flashcard-sets` | JWT | — | 200 list[FlashcardSetListItem] | 401, 404, 422 | List Flashcard Sets |
| `GET` | `/api/v1/flashcard-sets/{set_id}` | JWT | — | 200 FlashcardSetOut | 401, 404, 422 | Get Flashcard Set |
| `DELETE` | `/api/v1/flashcard-sets/{set_id}` | JWT | — | 204  | 401, 404, 422 | Delete Flashcard Set |
| `GET` | `/api/v1/flashcards/due` | JWT | — | 200 list[FlashcardOut] | 401, 404, 422 | Due Flashcards |
| `PATCH` | `/api/v1/flashcards/{card_id}` | JWT | FlashcardUpdate | 200 FlashcardOut | 401, 404, 422 | Update Flashcard |
| `GET` | `/api/v1/flashcards/{card_id}/reviews` | JWT | — | 200 list[ReviewOut] | 401, 404, 422 | Flashcard History |
| `GET` | `/api/v1/dashboard/summary` | JWT | — | 200 DashboardOut | 401, 404, 422 | Dashboard |
| `GET` | `/api/v1/usage` | JWT | — | 200 UsageOut | 401, 404, 422 | Usage |
## Key flows

**Upload → process.** `POST /workspaces/{id}/documents` (multipart `file`) returns `201` with `status: "UPLOADED"`.
Extraction, chunking and embedding run in the background; poll `GET /documents/{id}` until `READY` or `FAILED`
(`error_message` explains why, e.g. a scanned PDF). `POST /documents/{id}/process` re-runs ingestion.

**Chat.** `POST /workspaces/{id}/chat` with `{ "question": "...", "conversation_id": null, "document_ids": null }`.
The response contains the saved user and assistant messages; `message.citations[]` has `label`, `filename`,
`page_number`, `section_title`, `quote_text` and cosine `score`. When the materials do not support an answer,
`insufficient_evidence` is `true` and no citations are returned.

**Quiz.** `POST /workspaces/{id}/quizzes/generate` → questions **without** answers. `POST /quiz-attempts`
`{ "quiz_set_id" }` → attempt. `POST /quiz-attempts/{id}/submit` `{ "answers": { "<question_id>": "<option text | True | False | free text>" } }`
→ score, correct answers, explanations and source passages. Re-submitting returns 409.
