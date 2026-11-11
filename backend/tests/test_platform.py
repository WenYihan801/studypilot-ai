"""Dashboard, usage limits, rate limiting, account deletion, logging and the Gemini adapter."""

import logging
from types import SimpleNamespace

import pytest

from app.api import deps
from app.core.config import Settings, get_settings
from app.core.errors import AIProviderError
from app.core.logging import RedactSecretsFilter


def _set(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    get_settings.cache_clear()


# ---------------------------------------------------------------- dashboard
def test_dashboard_is_empty_for_new_user(client_a):
    d = client_a.get("/api/v1/dashboard/summary").json()
    assert d["total_workspaces"] == 0 and d["average_quiz_score"] is None
    assert len(d["activity_by_day"]) == 14 and all(x["count"] == 0 for x in d["activity_by_day"])


def test_dashboard_reflects_real_activity(client_a, client_b, workspace, ready_doc):
    client_a.post(f"/api/v1/workspaces/{workspace['id']}/chat", json={"question": "What is 1NF?"})
    quiz = client_a.post(
        f"/api/v1/workspaces/{workspace['id']}/quizzes/generate", json={"num_questions": 2, "types": ["true_false"]}
    ).json()
    att = client_a.post("/api/v1/quiz-attempts", json={"quiz_set_id": quiz["id"]}).json()
    answers = {q["id"]: "True" for q in quiz["questions"]}
    client_a.post(f"/api/v1/quiz-attempts/{att['id']}/submit", json={"answers": answers})
    client_a.post(f"/api/v1/workspaces/{workspace['id']}/flashcards/generate", json={"count": 3})

    d = client_a.get("/api/v1/dashboard/summary").json()
    assert d["total_workspaces"] == 1 and d["total_documents"] == 1 and d["total_quizzes"] == 1
    assert d["average_quiz_score"] == 100.0
    assert d["flashcards_to_review"] == 3
    assert d["total_study_sessions"] >= 4
    assert d["activity_by_day"][-1]["count"] >= 4
    assert d["quiz_scores"][0]["score"] == 100.0
    assert d["flashcard_mastery"]["NEW"] == 3
    # User B sees none of it
    assert client_b.get("/api/v1/dashboard/summary").json()["total_documents"] == 0


# ---------------------------------------------------------------- usage + limits
def test_usage_events_are_recorded(client_a, workspace, ready_doc):
    client_a.post(f"/api/v1/workspaces/{workspace['id']}/chat", json={"question": "What is 2NF?"})
    u = client_a.get("/api/v1/usage").json()
    ops = {o["operation"] for o in u["by_operation"]}
    assert {"embed_document", "embed_query", "chat"} <= ops
    assert u["requests_today"] >= 2 and u["tokens_today"] > 0


def test_daily_quota_blocks_ai_calls(client_a, workspace, ready_doc, monkeypatch):
    _set(monkeypatch, DAILY_AI_REQUEST_LIMIT=2)
    url = f"/api/v1/workspaces/{workspace['id']}/chat"
    assert client_a.post(url, json={"question": "What is 1NF?"}).status_code == 200  # embed_query + chat = 2
    r = client_a.post(url, json={"question": "What is 2NF?"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "quota_exceeded"
    # non-AI endpoints still work
    assert client_a.get("/api/v1/workspaces").status_code == 200


def test_per_minute_ai_rate_limit(client_a, workspace, ready_doc, monkeypatch):
    _set(monkeypatch, AI_RATE_LIMIT_PER_MINUTE=2)
    url = f"/api/v1/workspaces/{workspace['id']}/chat"
    codes = [client_a.post(url, json={"question": "What is 1NF?"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_daily_upload_limit(client_a, workspace, monkeypatch):
    _set(monkeypatch, DAILY_UPLOAD_LIMIT=1)
    from tests.conftest import upload

    assert upload(client_a, workspace["id"], "a.txt", b"one file", "text/plain").status_code == 201
    r = upload(client_a, workspace["id"], "b.txt", b"two files", "text/plain")
    assert r.status_code == 422 and r.json()["error"]["code"] == "upload_limit"


def test_users_cannot_write_integrity_tables_via_rls_policy_file():
    """Static check of the migration: scores/usage/activity are read-only for end users."""
    from pathlib import Path

    sql = next(Path(__file__).parents[2].glob("supabase/migrations/*_initial_schema.sql")).read_text()
    assert "array['quiz_attempts', 'quiz_answers', 'study_activities', 'ai_usage_events']" in sql
    assert "enable row level security" in sql
    assert "public, false" in sql.replace("'documents', 'documents', false", "public, false")


# ---------------------------------------------------------------- account deletion
def test_delete_account_removes_all_data(client_a, client_b, workspace, ready_doc):
    b_ws = client_b.post("/api/v1/workspaces", json={"name": "B keeps this"}).json()
    client_a.post(f"/api/v1/workspaces/{workspace['id']}/chat", json={"question": "1NF?"})
    assert client_a.delete("/api/v1/me").status_code == 204
    db = deps.memory_db
    for table in ("workspaces", "documents", "document_chunks", "messages", "ai_usage_events"):
        assert all(r.get("user_id") != "00000000-0000-0000-0000-000000000001" for r in db.select(table)), table
    assert deps.memory_storage.objects == {}
    assert client_b.get(f"/api/v1/workspaces/{b_ws['id']}").status_code == 200


# ---------------------------------------------------------------- errors + logging
def test_unknown_route_uses_error_envelope(client_a):
    r = client_a.get("/api/v1/nope")
    assert r.status_code == 404 and "error" in r.json()


def test_logs_never_contain_api_keys(caplog):
    f = RedactSecretsFilter(["AIzaSySECRETKEY123456"])
    rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "call failed key=%s", ("AIzaSySECRETKEY123456",), None)
    f.filter(rec)
    assert "AIzaSySECRETKEY123456" not in rec.getMessage() and "***" in rec.getMessage()


# ---------------------------------------------------------------- Gemini adapter (no network: fake SDK client)
class _FakeModels:
    def __init__(self, embed_dim=768, fail_times=0, text='{"answer":"x [S1]","cited_sources":["S1"],"sufficient_evidence":true}'):
        self.embed_dim, self.fail_times, self.text, self.calls = embed_dim, fail_times, text, 0

    def embed_content(self, model, contents, config):
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[3.0] + [4.0] + [0.0] * (self.embed_dim - 2)) for _ in contents]
        )

    def generate_content(self, model, contents, config):
        self.calls += 1
        if self.calls <= self.fail_times:
            from google.genai import errors

            raise errors.APIError(503, {"error": {"message": "overloaded"}})
        meta = SimpleNamespace(prompt_token_count=10, candidates_token_count=5, thoughts_token_count=None)
        return SimpleNamespace(text=self.text, usage_metadata=meta)


@pytest.fixture
def gemini(monkeypatch):
    from app.providers import gemini as gmod

    monkeypatch.setattr(gmod.time, "sleep", lambda s: None)
    provider = gmod.GeminiProvider(Settings(gemini_api_key="test-key", ai_provider="gemini"))
    provider._client = SimpleNamespace(models=_FakeModels())
    return provider


def test_gemini_embeddings_are_normalised(gemini):
    res = gemini.embed_texts(["a", "b"], task="document")
    assert len(res.vectors) == 2 and res.vectors[0][:2] == [0.6, 0.8]


def test_gemini_rejects_wrong_dimension(gemini):
    gemini._client.models.embed_dim = 3072
    with pytest.raises(AIProviderError, match="dimension"):
        gemini.embed_texts(["a"], task="query")


def test_gemini_structured_output_validated(gemini):
    from app.schemas.ai import ChatAnswerDraft

    res = gemini.generate_structured_output("p", ChatAnswerDraft)
    assert res.data.cited_sources == ["S1"] and res.usage.input_tokens == 10
    gemini._client.models.text = '{"answer": 42}'
    with pytest.raises(AIProviderError) as exc:
        gemini.generate_structured_output("p", ChatAnswerDraft)
    assert exc.value.code == "ai_invalid_output"


def test_gemini_retries_transient_errors_then_gives_up(gemini):
    gemini._client.models.fail_times = 1
    assert gemini.generate_text("hi").usage.output_tokens == 5  # recovered after 1 retry
    gemini._client.models.fail_times, gemini._client.models.calls = 99, 0
    with pytest.raises(AIProviderError):
        gemini.generate_text("hi")
    assert gemini._client.models.calls == 3  # bounded: 1 + AI_MAX_RETRIES(2)
