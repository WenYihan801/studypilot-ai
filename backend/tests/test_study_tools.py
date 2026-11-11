"""Summaries, quizzes (generation, validation, scoring) and flashcards."""

import pytest

from app.api import deps
from app.schemas.ai import QuizQuestionDraft
from app.services.quiz import check_question


# ---------------------------------------------------------------- summary
def test_summary_is_structured_and_cached(client_a, ready_doc):
    r = client_a.post(f"/api/v1/documents/{ready_doc['id']}/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cached"] is False
    s = body["summary"]
    for key in (
        "overview",
        "main_topics",
        "key_concepts",
        "important_definitions",
        "important_arguments",
        "key_takeaways",
        "revision_checklist",
        "source_references",
    ):
        assert key in s
    assert s["source_references"][0]["filename"] == "db-notes.md"
    calls_before = len(deps.memory_db.select("ai_usage_events"))
    again = client_a.post(f"/api/v1/documents/{ready_doc['id']}/summary").json()
    assert again["cached"] is True
    assert len(deps.memory_db.select("ai_usage_events")) == calls_before  # cache hit: no AI call
    forced = client_a.post(f"/api/v1/documents/{ready_doc['id']}/summary", json={"force": True}).json()
    assert forced["cached"] is False
    assert client_a.get(f"/api/v1/documents/{ready_doc['id']}/summary").json()["cached"] is True


def test_long_documents_are_summarised_in_parts(client_a, workspace, monkeypatch):
    text = "\n\n".join(
        f"# Chapter {i}\n" + " ".join(f"Concept {i}.{j} is described in detail here." for j in range(120)) for i in range(6)
    )
    from tests.conftest import upload

    doc = upload(client_a, workspace["id"], "book.md", text.encode(), "text/markdown").json()
    from app.providers.mock import MockProvider

    calls = []
    orig = MockProvider.generate_text
    monkeypatch.setattr(MockProvider, "generate_text", lambda self, p, **kw: calls.append(len(p)) or orig(self, p, **kw))
    client_a.post(f"/api/v1/documents/{doc['id']}/summary")
    assert len(calls) >= 2  # map step ran per group
    assert max(calls) < 20000  # no single call gets the whole document


def test_summary_requires_ready_document(client_a, workspace):
    from tests.conftest import upload
    from tests.helpers import make_blank_pdf

    doc = upload(client_a, workspace["id"], "scan.pdf", make_blank_pdf(), "application/pdf").json()
    r = client_a.post(f"/api/v1/documents/{doc['id']}/summary")
    assert r.status_code == 422 and r.json()["error"]["code"] == "document_not_ready"


# ---------------------------------------------------------------- quiz validation (unit)
LABELS = {"S1": {"id": "chunk-1"}}


def _q(**kw):
    base = dict(
        type="multiple_choice",
        question="Which is true?",
        options=["A", "B", "C", "D"],
        correct_answer="b",
        explanation="Because.",
        difficulty="easy",
        source_labels=["S1"],
    )
    return QuizQuestionDraft(**{**base, **kw})


def test_check_question_accepts_and_normalises():
    q = check_question(_q(), {"multiple_choice"}, LABELS)
    assert q and q.correct_answer == "B"
    tf = check_question(_q(type="true_false", options=[], correct_answer="false"), {"true_false"}, LABELS)
    assert tf and tf.options == ["True", "False"] and tf.correct_answer == "False"


@pytest.mark.parametrize(
    "bad",
    [
        {"options": ["A", "B", "C"]},  # wrong option count
        {"options": ["A", "A", "C", "D"]},  # duplicate options
        {"correct_answer": "E"},  # answer not in options
        {"source_labels": ["S9"]},  # invented source
        {"type": "short_answer"},  # type not requested
    ],
)
def test_check_question_rejects_invalid(bad):
    assert check_question(_q(**bad), {"multiple_choice"}, LABELS) is None


# ---------------------------------------------------------------- quiz flow (API)
def _gen(client, wid, **kw):
    body = {"num_questions": 4, "difficulty": "easy", "types": ["multiple_choice", "true_false"], **kw}
    return client.post(f"/api/v1/workspaces/{wid}/quizzes/generate", json=body)


def test_generate_quiz_hides_answers_until_submitted(client_a, workspace, ready_doc):
    r = _gen(client_a, workspace["id"], title="Week 3")
    assert r.status_code == 201, r.text
    quiz = r.json()
    assert quiz["title"] == "Week 3" and len(quiz["questions"]) == 4
    assert all("correct_answer" not in q and "explanation" not in q for q in quiz["questions"])
    stored = deps.memory_db.select("quiz_questions")
    assert all(q["source_chunk_ids"] for q in stored)


def test_quiz_attempt_scoring_and_results(client_a, workspace, ready_doc):
    quiz = _gen(client_a, workspace["id"]).json()
    attempt = client_a.post("/api/v1/quiz-attempts", json={"quiz_set_id": quiz["id"]}).json()
    stored = {q["id"]: q for q in deps.memory_db.select("quiz_questions")}
    answers = {}
    for i, q in enumerate(quiz["questions"]):
        correct = stored[q["id"]]["correct_answer"]
        answers[q["id"]] = correct if i < 3 else "definitely wrong"
    r = client_a.post(f"/api/v1/quiz-attempts/{attempt['id']}/submit", json={"answers": answers})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["attempt"]["score"] == 75.0
    assert sum(i["is_correct"] for i in res["items"]) == 3
    item = res["items"][0]
    assert item["correct_answer"] and item["explanation"] and item["sources"][0]["filename"] == "db-notes.md"
    # result page reload
    assert client_a.get(f"/api/v1/quiz-attempts/{attempt['id']}").json()["attempt"]["score"] == 75.0
    # cannot resubmit
    assert client_a.post(f"/api/v1/quiz-attempts/{attempt['id']}/submit", json={"answers": answers}).status_code == 409


def test_short_answer_grading(client_a, workspace, ready_doc):
    quiz = _gen(client_a, workspace["id"], types=["short_answer"], num_questions=2).json()
    attempt = client_a.post("/api/v1/quiz-attempts", json={"quiz_set_id": quiz["id"]}).json()
    stored = {q["id"]: q for q in deps.memory_db.select("quiz_questions")}
    q1, q2 = quiz["questions"]
    answers = {q1["id"]: stored[q1["id"]]["correct_answer"], q2["id"]: "bananas"}
    res = client_a.post(f"/api/v1/quiz-attempts/{attempt['id']}/submit", json={"answers": answers}).json()
    assert [i["is_correct"] for i in res["items"]] == [True, False]
    assert res["items"][1]["feedback"]


def test_quiz_requires_ready_documents(client_a, workspace):
    r = _gen(client_a, workspace["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_ready_documents"


def test_quiz_question_count_limit(client_a, workspace, ready_doc):
    assert _gen(client_a, workspace["id"], num_questions=21).status_code == 422


def test_quiz_isolation(client_a, client_b, workspace, ready_doc):
    quiz = _gen(client_a, workspace["id"]).json()
    assert client_b.get(f"/api/v1/quizzes/{quiz['id']}").status_code == 404
    assert client_b.post("/api/v1/quiz-attempts", json={"quiz_set_id": quiz["id"]}).status_code == 404
    attempt = client_a.post("/api/v1/quiz-attempts", json={"quiz_set_id": quiz["id"]}).json()
    assert client_b.post(f"/api/v1/quiz-attempts/{attempt['id']}/submit", json={"answers": {}}).status_code == 404


def test_quiz_list_shows_best_score(client_a, workspace, ready_doc):
    quiz = _gen(client_a, workspace["id"], num_questions=2).json()
    attempt = client_a.post("/api/v1/quiz-attempts", json={"quiz_set_id": quiz["id"]}).json()
    client_a.post(f"/api/v1/quiz-attempts/{attempt['id']}/submit", json={"answers": {}})
    listed = client_a.get(f"/api/v1/workspaces/{workspace['id']}/quizzes").json()
    assert listed[0]["attempt_count"] == 1 and listed[0]["best_score"] == 0.0


# ---------------------------------------------------------------- flashcards
def test_flashcard_generate_review_and_history(client_a, workspace, ready_doc):
    r = client_a.post(f"/api/v1/workspaces/{workspace['id']}/flashcards/generate", json={"count": 5})
    assert r.status_code == 201, r.text
    fs = r.json()
    assert len(fs["cards"]) == 5
    assert all(c["mastery_status"] == "NEW" and c["source"]["filename"] == "db-notes.md" for c in fs["cards"])

    card = fs["cards"][0]
    r = client_a.patch(f"/api/v1/flashcards/{card['id']}", json={"mastery_status": "LEARNING"})
    assert r.json()["mastery_status"] == "LEARNING" and r.json()["reviewed_at"]
    client_a.patch(f"/api/v1/flashcards/{card['id']}", json={"mastery_status": "MASTERED"})
    history = client_a.get(f"/api/v1/flashcards/{card['id']}/reviews").json()
    assert [(h["previous_status"], h["new_status"]) for h in history] == [("LEARNING", "MASTERED"), ("NEW", "LEARNING")]

    due = client_a.get("/api/v1/flashcards/due").json()
    assert len(due) == 4 and card["id"] not in {c["id"] for c in due}
    sets = client_a.get(f"/api/v1/workspaces/{workspace['id']}/flashcard-sets").json()
    assert sets[0]["card_count"] == 5 and sets[0]["mastered_count"] == 1


def test_flashcard_validation_and_isolation(client_a, client_b, workspace, ready_doc):
    fs = client_a.post(f"/api/v1/workspaces/{workspace['id']}/flashcards/generate", json={"count": 2}).json()
    cid = fs["cards"][0]["id"]
    assert client_a.patch(f"/api/v1/flashcards/{cid}", json={"mastery_status": "DONE"}).status_code == 422
    assert client_b.patch(f"/api/v1/flashcards/{cid}", json={"mastery_status": "MASTERED"}).status_code == 404
    assert client_b.get(f"/api/v1/flashcard-sets/{fs['id']}").status_code == 404
    assert client_a.post(f"/api/v1/workspaces/{workspace['id']}/flashcards/generate", json={"count": 31}).status_code == 422
