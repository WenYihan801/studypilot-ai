from collections import Counter
from datetime import UTC, datetime, timedelta

from app.api.deps import Ctx
from app.db.gateway import Op, gte, neq
from app.repositories import (
    ActivityRepo,
    DocumentRepo,
    FlashcardRepo,
    QuizAttemptRepo,
    QuizSetRepo,
    WorkspaceRepo,
)

PROGRESS_DAYS = 14


class DashboardService:
    """Every number comes from the database; nothing is hard-coded."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    def summary(self) -> dict:
        uid, db = self.ctx.user_id, self.ctx.db
        attempts = QuizAttemptRepo(db).list(uid, {"submitted_at": Op("not_null")}, limit=500)
        scores = [a["score"] for a in attempts if a["score"] is not None]
        since = (datetime.now(UTC) - timedelta(days=PROGRESS_DAYS - 1)).date()
        activities = ActivityRepo(db).list(uid, {"created_at": gte(since.isoformat())}, limit=2000)
        per_day = Counter(str(a["created_at"])[:10] for a in activities)
        cards = FlashcardRepo(db).list(uid, columns="id,mastery_status")
        mastery = Counter(c["mastery_status"] for c in cards)
        quiz_titles = {q["id"]: q["title"] for q in QuizSetRepo(db).list(uid, columns="id,title")}

        return {
            "total_workspaces": WorkspaceRepo(db).count(uid),
            "total_documents": DocumentRepo(db).count(uid),
            "total_study_sessions": ActivityRepo(db).count(uid),
            "total_quizzes": len(quiz_titles),
            "average_quiz_score": round(sum(scores) / len(scores), 1) if scores else None,
            "flashcards_to_review": FlashcardRepo(db).count(uid, {"mastery_status": neq("MASTERED")}),
            "recent_activity": ActivityRepo(db).list(uid, limit=10),
            "activity_by_day": [
                {
                    "date": (since + timedelta(days=i)).isoformat(),
                    "count": per_day.get((since + timedelta(days=i)).isoformat(), 0),
                }
                for i in range(PROGRESS_DAYS)
            ],
            "quiz_scores": [
                {
                    "attempt_id": a["id"],
                    "title": quiz_titles.get(a["quiz_set_id"], "Quiz"),
                    "score": a["score"],
                    "submitted_at": a["submitted_at"],
                }
                for a in sorted(attempts, key=lambda a: str(a["submitted_at"]))[-10:]
            ],
            "flashcard_mastery": {k: mastery.get(k, 0) for k in ("NEW", "LEARNING", "MASTERED")},
        }
