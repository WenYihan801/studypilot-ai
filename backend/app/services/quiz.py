from __future__ import annotations

from datetime import UTC, datetime

from app.api.deps import Ctx
from app.core.errors import AIProviderError, ConflictError, ValidationFailedError
from app.db.gateway import in_
from app.repositories import (
    ChunkRepo,
    DocumentRepo,
    QuizAnswerRepo,
    QuizAttemptRepo,
    QuizQuestionRepo,
    QuizSetRepo,
    WorkspaceRepo,
)
from app.schemas.ai import QuizDraft, QuizQuestionDraft, ShortAnswerGrades
from app.services.context import sample_chunks
from app.services.prompts import (
    GRADING_SYSTEM,
    QUIZ_SYSTEM,
    format_sources,
    grading_prompt,
    quiz_prompt,
)
from app.services.usage import ActivityService, UsageService


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def check_question(q: QuizQuestionDraft, allowed_types: set[str], label_map: dict) -> QuizQuestionDraft | None:
    """Business validation on top of Pydantic. Returns a cleaned question, or None to discard it."""
    if q.type not in allowed_types:
        return None
    if q.type == "multiple_choice":
        opts = [o.strip() for o in q.options if o.strip()]
        if len(opts) != 4 or len({_norm(o) for o in opts}) != 4:
            return None
        match = [o for o in opts if _norm(o) == _norm(q.correct_answer)]
        if not match:
            return None
        q = q.model_copy(update={"options": opts, "correct_answer": match[0]})
    elif q.type == "true_false":
        ans = _norm(q.correct_answer)
        if ans not in ("true", "false"):
            return None
        q = q.model_copy(update={"options": ["True", "False"], "correct_answer": ans.capitalize()})
    else:
        q = q.model_copy(update={"options": []})
    labels = [lbl for lbl in q.source_labels if lbl in label_map]
    if not labels:
        return None  # every question must be traceable to retrieved material
    return q.model_copy(update={"source_labels": labels})


class QuizService:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.sets = QuizSetRepo(ctx.db)
        self.questions = QuizQuestionRepo(ctx.db)
        # Attempts/answers are integrity tables: written with admin client + explicit user_id.
        self.attempts = QuizAttemptRepo(ctx.admin)
        self.answers = QuizAnswerRepo(ctx.admin)
        self.usage = UsageService(ctx.admin, ctx.settings)

    # ------------------------------------------------------------------ generate
    def generate(
        self,
        workspace_id: str,
        *,
        title: str | None,
        num_questions: int,
        difficulty: str,
        types: list[str],
        document_ids: list[str] | None,
    ) -> dict:
        uid, s = self.ctx.user_id, self.ctx.settings
        WorkspaceRepo(self.ctx.db).get(uid, workspace_id)
        if not 1 <= num_questions <= s.max_quiz_questions:
            raise ValidationFailedError(f"Number of questions must be between 1 and {s.max_quiz_questions}.")
        self.usage.check_quota(uid)
        chunks = sample_chunks(self.ctx, workspace_id, document_ids, max_chunks=min(16, num_questions + 6))
        block, label_map = format_sources(chunks)

        result = self.ctx.ai.generate_structured_output(
            quiz_prompt(block, num_questions, types, difficulty),
            QuizDraft,
            system=QUIZ_SYSTEM,
            role="quiz",
            max_output_tokens=min(8000, 500 * num_questions + 500),
        )
        self.usage.record(uid, self.ctx.ai.name, "quiz_generate", result.usage)
        valid = [q for q in (check_question(q, set(types), label_map) for q in result.data.questions) if q]
        valid = valid[:num_questions]
        if not valid:
            raise AIProviderError("The AI did not produce any valid questions. Please try again.", code="ai_invalid_output")

        settings_json = {
            "num_questions": num_questions,
            "difficulty": difficulty,
            "types": types,
            "document_ids": document_ids or [],
            "generated": len(valid),
            "model": result.usage.model,
        }
        qs = self.sets.create(
            uid,
            {
                "workspace_id": workspace_id,
                "settings_json": settings_json,
                "title": (title or "").strip() or f"Quiz – {datetime.now(UTC):%d %b %Y %H:%M}",
            },
        )
        self.questions.create_many(
            uid,
            [
                {
                    "quiz_set_id": qs["id"],
                    "position": i,
                    "type": q.type,
                    "question": q.question,
                    "options_json": q.options,
                    "correct_answer": q.correct_answer,
                    "explanation": q.explanation,
                    "difficulty": q.difficulty,
                    "source_chunk_ids": [label_map[lbl]["id"] for lbl in q.source_labels],
                }
                for i, q in enumerate(valid)
            ],
        )
        ActivityService(self.ctx.admin).log(uid, workspace_id, "quiz_generated", f"Generated quiz '{qs['title']}'")
        return self.get(qs["id"])

    # ------------------------------------------------------------------ reads
    def list(self, workspace_id: str) -> list[dict]:
        WorkspaceRepo(self.ctx.db).get(self.ctx.user_id, workspace_id)
        sets = self.sets.list(self.ctx.user_id, {"workspace_id": workspace_id})
        attempts = self.attempts.list(self.ctx.user_id, {"quiz_set_id": in_([s["id"] for s in sets])}) if sets else []
        out = []
        for qs in sets:
            done = [a for a in attempts if a["quiz_set_id"] == qs["id"] and a["submitted_at"]]
            out.append(
                {
                    **qs,
                    "question_count": qs["settings_json"].get("generated", 0),
                    "attempt_count": len(done),
                    "best_score": max((a["score"] for a in done), default=None),
                }
            )
        return out

    def get(self, quiz_set_id: str) -> dict:
        """Questions WITHOUT answers – answers are only revealed in a submitted attempt."""
        qs = self.sets.get(self.ctx.user_id, quiz_set_id)
        qs_questions = self.questions.list(self.ctx.user_id, {"quiz_set_id": quiz_set_id})
        return {
            **qs,
            "questions": [
                {
                    "id": q["id"],
                    "position": q["position"],
                    "type": q["type"],
                    "question": q["question"],
                    "options": q["options_json"],
                    "difficulty": q["difficulty"],
                }
                for q in qs_questions
            ],
        }

    def delete(self, quiz_set_id: str) -> None:
        self.sets.delete(self.ctx.user_id, quiz_set_id)

    # ------------------------------------------------------------------ attempts
    def start_attempt(self, quiz_set_id: str) -> dict:
        self.sets.get(self.ctx.user_id, quiz_set_id)
        return self.attempts.create(self.ctx.user_id, {"quiz_set_id": quiz_set_id})

    def submit(self, attempt_id: str, answers: dict[str, str]) -> dict:
        uid = self.ctx.user_id
        attempt = self.attempts.get(uid, attempt_id)
        if attempt["submitted_at"]:
            raise ConflictError("This attempt was already submitted.", code="already_submitted")
        questions = self.questions.list(uid, {"quiz_set_id": attempt["quiz_set_id"]})
        unknown = set(answers) - {q["id"] for q in questions}
        if unknown:
            raise ValidationFailedError("Answers reference questions that are not part of this quiz.")

        graded: dict[str, tuple[bool, str]] = {}
        short_items = []
        for q in questions:
            given = (answers.get(q["id"]) or "").strip()
            if q["type"] == "short_answer":
                if given:
                    short_items.append(
                        {"id": q["id"], "question": q["question"], "reference": q["correct_answer"], "answer": given}
                    )
                else:
                    graded[q["id"]] = (False, "No answer given.")
            else:
                ok = _norm(given) == _norm(q["correct_answer"])
                graded[q["id"]] = (ok, "Correct." if ok else f"The correct answer is: {q['correct_answer']}")

        if short_items:
            self.usage.check_quota(uid)
            res = self.ctx.ai.generate_structured_output(
                grading_prompt(short_items), ShortAnswerGrades, system=GRADING_SYSTEM, max_output_tokens=1500
            )
            self.usage.record(uid, self.ctx.ai.name, "quiz_grade", res.usage)
            by_id = {g.question_id: g for g in res.data.grades}
            for it in short_items:
                g = by_id.get(it["id"])
                # If the model skipped an item, fail safe: mark incorrect and say so.
                graded[it["id"]] = (g.is_correct, g.feedback) if g else (False, "Could not be graded automatically.")

        self.answers.create_many(
            uid,
            [
                {
                    "attempt_id": attempt_id,
                    "question_id": q["id"],
                    "answer_json": {"answer": answers.get(q["id"], "")},
                    "is_correct": graded[q["id"]][0],
                    "feedback": graded[q["id"]][1],
                }
                for q in questions
            ],
        )
        correct = sum(1 for v in graded.values() if v[0])
        score = round(100 * correct / len(questions), 1) if questions else 0.0
        self.attempts.update(uid, attempt_id, {"score": score, "submitted_at": datetime.now(UTC).isoformat()})
        qs = self.sets.get(uid, attempt["quiz_set_id"])
        ActivityService(self.ctx.admin).log(uid, qs["workspace_id"], "quiz_submitted", f"Scored {score:g}% on '{qs['title']}'")
        return self.result(attempt_id)

    def result(self, attempt_id: str) -> dict:
        uid = self.ctx.user_id
        attempt = self.attempts.get(uid, attempt_id)
        qs = self.sets.get(uid, attempt["quiz_set_id"])
        questions = self.questions.list(uid, {"quiz_set_id": qs["id"]})
        if not attempt["submitted_at"]:
            return {"attempt": attempt, "quiz": {"id": qs["id"], "title": qs["title"]}, "items": []}
        answers = {a["question_id"]: a for a in self.answers.list(uid, {"attempt_id": attempt_id})}
        chunk_ids = list({cid for q in questions for cid in (q["source_chunk_ids"] or [])})
        chunks = (
            {
                c["id"]: c
                for c in ChunkRepo(self.ctx.db).list(
                    uid, {"id": in_(chunk_ids)}, columns="id,document_id,content,page_number,section_title"
                )
            }
            if chunk_ids
            else {}
        )
        doc_ids = list({c["document_id"] for c in chunks.values()})
        docs = (
            {d["id"]: d["filename"] for d in DocumentRepo(self.ctx.db).list(uid, {"id": in_(doc_ids)}, columns="id,filename")}
            if doc_ids
            else {}
        )
        items = []
        for q in questions:
            a = answers.get(q["id"], {})
            items.append(
                {
                    "question_id": q["id"],
                    "position": q["position"],
                    "type": q["type"],
                    "question": q["question"],
                    "options": q["options_json"],
                    "difficulty": q["difficulty"],
                    "your_answer": (a.get("answer_json") or {}).get("answer", ""),
                    "is_correct": a.get("is_correct", False),
                    "feedback": a.get("feedback", ""),
                    "correct_answer": q["correct_answer"],
                    "explanation": q["explanation"],
                    "sources": [
                        {
                            "chunk_id": cid,
                            "filename": docs.get(chunks[cid]["document_id"], "Deleted document"),
                            "page_number": chunks[cid]["page_number"],
                            "section_title": chunks[cid]["section_title"],
                            "quote_text": chunks[cid]["content"][:300],
                        }
                        for cid in (q["source_chunk_ids"] or [])
                        if cid in chunks
                    ],
                }
            )
        return {
            "attempt": attempt,
            "quiz": {"id": qs["id"], "title": qs["title"], "workspace_id": qs["workspace_id"]},
            "items": items,
        }
