"""Checks that backend/.env can reach Supabase and Gemini. Never prints secret values.

cd backend && uv run python scripts/check_connections.py
"""

import sys
import time

sys.path.insert(0, ".")

from app.core.config import get_settings  # noqa: E402

s = get_settings()
results: list[tuple[str, bool, str]] = []


def check(name, fn):
    try:
        detail = fn() or ""
        results.append((name, True, detail))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        for secret in s.secret_values():
            msg = msg.replace(secret, "***")
        results.append((name, False, f"{type(exc).__name__}: {msg[:300]}"))


def env_present():
    missing = [
        k
        for k, v in {
            "SUPABASE_URL": s.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": s.supabase_publishable_key,
            "SUPABASE_SECRET_KEY": s.supabase_secret_key,
            "GEMINI_API_KEY": s.gemini_api_key,
        }.items()
        if not v
    ]
    if missing:
        raise RuntimeError("empty in .env: " + ", ".join(missing))
    return f"AI_PROVIDER={s.ai_provider}"


def jwks():
    import httpx

    keys = httpx.get(s.supabase_jwks_url, timeout=15).raise_for_status().json()["keys"]
    algs = sorted({k.get("alg") for k in keys})
    if not ({"ES256", "RS256"} & set(algs)):
        raise RuntimeError(f"no asymmetric signing key, found {algs}")
    return f"algorithms {algs}"


def database():
    from app.db.supabase_gateway import SupabaseGateway

    db = SupabaseGateway.admin(s.supabase_url, s.supabase_secret_key)
    n = db.count("workspaces")
    db.select("document_chunks", columns="id", limit=1)
    return f"tables reachable (workspaces rows: {n})"


def storage():
    from supabase import create_client

    buckets = create_client(s.supabase_url, s.supabase_secret_key).storage.list_buckets()
    b = next((b for b in buckets if b.id == s.storage_bucket), None)
    if b is None:
        raise RuntimeError(f"bucket '{s.storage_bucket}' not found")
    if b.public:
        raise RuntimeError("bucket is PUBLIC - it must be private")
    return "bucket 'documents' exists and is private"


def gemini_embed():
    from app.providers.gemini import GeminiProvider

    res = GeminiProvider(s).embed_texts(["Database normalization reduces redundancy."], task="document")
    v = res.vectors[0]
    norm = sum(x * x for x in v) ** 0.5
    return f"{s.gemini_embedding_model}: {len(v)} dims, norm={norm:.3f}"


def gemini_text(role):
    def run():
        from app.providers.gemini import GeminiProvider

        t0 = time.time()
        res = GeminiProvider(s).generate_text("Reply with exactly: OK", role=role, max_output_tokens=512)
        model = s.gemini_quiz_model if role == "quiz" else s.gemini_chat_model
        return f"{model}: replied {res.text.strip()[:20]!r} in {time.time() - t0:.1f}s"

    return run


check("1. .env values present", env_present)
check("2. Supabase JWKS (login token verification)", jwks)
check("3. Supabase database via secret key", database)
check("4. Supabase storage bucket", storage)
check("5. Gemini embeddings", gemini_embed)
check("6. Gemini chat model", gemini_text("chat"))
check("7. Gemini quiz model", gemini_text("quiz"))

print()
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
print()
print("ALL PASSED" if all(ok for _, ok, _ in results) else "SOME CHECKS FAILED - copy the FAIL lines (they contain no secrets)")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
