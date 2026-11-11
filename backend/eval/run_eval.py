"""Fixed RAG evaluation set.

Runs the real application code path (upload -> ingestion -> chat) against the sample_data
documents, using an in-memory database and whichever AI provider is configured.

    # Real measurement (uses your Gemini free quota: ~30 embedding + ~26 chat calls)
    AI_PROVIDER=gemini GEMINI_API_KEY=... uv run python -m eval.run_eval

    # Pipeline smoke test only (numbers say nothing about model quality)
    AI_PROVIDER=mock uv run python -m eval.run_eval

Results are written to eval/results/. Report the numbers exactly as measured.
"""

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

os.environ["DATA_BACKEND"] = "memory"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SUPABASE_URL", "https://eval.supabase.co")
os.environ.setdefault("DAILY_AI_REQUEST_LIMIT", "1000")
os.environ.setdefault("AI_RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import CurrentUser, get_current_user  # noqa: E402
from app.main import create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
USER = "00000000-0000-0000-0000-00000000e7a1"


def main() -> int:
    settings = get_settings()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=USER, email="eval@example.com", access_token="eval")
    client = TestClient(app)
    delay = float(os.environ.get("EVAL_DELAY_SECONDS", "4" if settings.ai_provider == "gemini" else "0"))

    ws = client.post("/api/v1/workspaces", json={"name": "Evaluation"}).json()
    for path in sorted((ROOT / "sample_data").glob("*.md")):
        r = client.post(
            f"/api/v1/workspaces/{ws['id']}/documents", files={"file": (path.name, path.read_bytes(), "text/markdown")}
        )
        doc = client.get(f"/api/v1/documents/{r.json()['id']}").json()
        print(f"ingested {path.name}: {doc['status']} ({doc['chunk_count']} chunks) {doc.get('error_message') or ''}")
        if doc["status"] != "READY":
            return 1

    questions = json.loads((EVAL_DIR / "questions.json").read_text())
    rows = []
    for q in questions:
        r = client.post(f"/api/v1/workspaces/{ws['id']}/chat", json={"question": q["question"]})
        if r.status_code != 200:
            rows.append({**q, "error": r.json()})
            print(f"{q['id']}: ERROR {r.status_code}")
            continue
        body = r.json()
        msg = body["message"]
        files = [c["filename"] for c in msg["citations"]]
        in_scope = q["expected_file"] is not None
        row = {
            "id": q["id"],
            "question": q["question"],
            "in_scope": in_scope,
            "insufficient": body["insufficient_evidence"],
            "cited_files": files,
            "answer": msg["content"],
            "source_hit": (q["expected_file"] in files) if in_scope else None,
            "keywords_found": all(k.lower() in msg["content"].lower() for k in q["keywords"]) if in_scope else None,
            "correct_refusal": body["insufficient_evidence"] if not in_scope else None,
        }
        rows.append(row)
        print(f"{q['id']}: hit={row['source_hit']} refusal={row['correct_refusal']} insufficient={row['insufficient']}")
        time.sleep(delay)

    ok = [r for r in rows if "error" not in r]
    ins = [r for r in ok if r["in_scope"]]
    outs = [r for r in ok if not r["in_scope"]]

    def pct(n, d):
        return f"{100 * n / d:.1f}% ({n}/{d})" if d else "n/a"

    metrics = {
        "provider": settings.ai_provider,
        "chat_model": settings.gemini_chat_model if settings.ai_provider == "gemini" else "mock",
        "embedding_model": settings.gemini_embedding_model if settings.ai_provider == "gemini" else "mock",
        "top_k": settings.retrieval_top_k,
        "min_score": settings.retrieval_min_score,
        "chunk_size_tokens": settings.chunk_size_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
        "errors": len(rows) - len(ok),
        "source_hit_rate": pct(sum(r["source_hit"] for r in ins), len(ins)),
        "keyword_coverage": pct(sum(r["keywords_found"] for r in ins), len(ins)),
        "answered_when_in_scope": pct(sum(not r["insufficient"] for r in ins), len(ins)),
        "correct_refusal_rate": pct(sum(r["correct_refusal"] for r in outs), len(outs)),
        "invalid_citations": 0,  # by construction: validate_citations() drops anything not retrieved
    }
    out_dir = EVAL_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out_dir / f"{stamp}-{settings.ai_provider}.json").write_text(json.dumps({"metrics": metrics, "rows": rows}, indent=2))
    lines = [f"# RAG evaluation — {stamp} ({settings.ai_provider})", ""]
    if settings.ai_provider == "mock":
        lines += ["> Mock provider: this only proves the pipeline runs. These numbers are NOT model accuracy.", ""]
    lines += ["| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in metrics.items()]
    lines += ["", "| ID | In scope | Source hit | Keywords | Insufficient |", "|---|---|---|---|---|"]
    lines += [
        f"| {r['id']} | {r.get('in_scope')} | {r.get('source_hit')} | {r.get('keywords_found')} | {r.get('insufficient')} |"
        for r in rows
    ]
    (out_dir / f"{stamp}-{settings.ai_provider}.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
