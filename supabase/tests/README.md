# SQL checks

`00_supabase_stubs.sql` creates minimal stand-ins for Supabase's `auth` and `storage` schemas so the
migration can be executed on plain PostgreSQL 16 + pgvector (useful in CI). `10_rls_check.sql` then
impersonates two users and shows that RLS blocks cross-user reads/writes, forged usage events and
foreign vector search. Expected output: B sees 0 rows, three "violates row-level security" errors,
A match_chunks = 1, B match_chunks = 0, chunks after delete = 0.

```bash
createdb sp_check
psql -d sp_check -f supabase/tests/00_supabase_stubs.sql
psql -d sp_check -v ON_ERROR_STOP=1 -f supabase/migrations/20261111000001_initial_schema.sql
psql -d sp_check -t -f supabase/tests/10_rls_check.sql
```

Against the real Supabase project, use `backend/tests/integration/test_rls_live.py` instead.
