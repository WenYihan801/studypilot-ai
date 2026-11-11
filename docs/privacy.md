# Privacy, Security & AI Data Use

## What users are told (also shown in the app at `/privacy`, at sign-up and in Settings)

1. Text extracted from uploaded documents, and every question, is sent to **Google's Gemini API** (a third-party AI provider)
   for embeddings, answers, summaries, quizzes and flashcards.
2. On the **free API tier**, Google's pricing page states that content may be used to improve Google's products; on the paid
   tier it is not. Free and paid terms differ.
3. Use **public or self-made** materials for demos. Do not upload confidential, personal or sensitive documents.

## Security controls

| Control | Implementation |
|---|---|
| HTTPS | Vercel and Render terminate TLS; Supabase endpoints are HTTPS only |
| Authentication | Supabase Auth; backend verifies JWT signature via JWKS (ES256/RS256), `exp`, `aud`, `iss`; HS256 rejected |
| Authorization | Ownership filter in every repository call **and** PostgreSQL RLS (backend reads with the user's JWT) |
| Integrity tables | Scores, usage and activity are read-only through the public API; only the backend writes them |
| Storage | Private bucket; path prefix `{user_id}/…`; storage RLS policies; files are never served publicly |
| Secrets | `SUPABASE_SECRET_KEY` and `GEMINI_API_KEY` exist only in backend env (Render). The browser gets only the publishable key |
| CORS | Explicit origin allowlist (`CORS_ORIGINS`), no wildcard, no cookies |
| Upload validation | Extension allowlist, declared MIME check, magic-byte check (PDF/ZIP-DOCX/UTF-8 text), executable signatures rejected, 20 MB cap, SHA-256 duplicate check |
| Prompt injection | Retrieved text is wrapped in `<sources>` and the system prompt says it is untrusted data, not instructions (tested) |
| Output safety | AI answers are rendered by a React-element Markdown renderer — no `innerHTML`, so model output cannot inject scripts (tested) |
| Abuse limits | 60 req/min/user, 10 AI req/min/user, 100 AI requests/day/user, 30 uploads/day, question ≤ 2,000 chars |
| Logging | A logging filter replaces configured secret values with `***`; unhandled errors return a generic message |
| Error leakage | Resources owned by others return 404, not 403 |
| Deletion | Document → file + vectors + summary; workspace → everything inside; account → all files, rows, then the auth user |

## Data retention

Data is kept until the user deletes it. Supabase free projects may be paused after inactivity (data is kept).
`ai_usage_events` are deleted with the account.
