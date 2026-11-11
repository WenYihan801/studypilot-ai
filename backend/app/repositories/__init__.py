"""Repository layer: table access with ownership checks built in.

Every method takes the owner `user_id` and adds it to the filter. With the user-scoped
Supabase client this is defence in depth on top of RLS; with the admin client it is the
primary isolation guarantee.
"""

from __future__ import annotations

from app.core.errors import NotFoundError
from app.db.gateway import Filters, Gateway, Order


class TableRepo:
    table: str = ""
    label: str = "Resource"
    default_order: Order | None = Order("created_at", desc=True)

    def __init__(self, db: Gateway):
        self.db = db

    def list(
        self,
        user_id: str,
        filters: Filters | None = None,
        *,
        columns: str = "*",
        order: Order | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return self.db.select(
            self.table, {"user_id": user_id, **(filters or {})}, columns=columns, order=order or self.default_order, limit=limit
        )

    def find(self, user_id: str, id_: str, *, columns: str = "*") -> dict | None:
        rows = self.db.select(self.table, {"id": id_, "user_id": user_id}, columns=columns, limit=1)
        return rows[0] if rows else None

    def get(self, user_id: str, id_: str, *, columns: str = "*") -> dict:
        row = self.find(user_id, id_, columns=columns)
        if row is None:
            # Same response whether the row is missing or belongs to someone else: no existence leak.
            raise NotFoundError(f"{self.label} not found.")
        return row

    def create(self, user_id: str, values: dict) -> dict:
        return self.db.insert(self.table, [{**values, "user_id": user_id}])[0]

    def create_many(self, user_id: str, rows: list[dict]) -> list[dict]:
        return self.db.insert(self.table, [{**r, "user_id": user_id} for r in rows])

    def update(self, user_id: str, id_: str, values: dict) -> dict:
        rows = self.db.update(self.table, {"id": id_, "user_id": user_id}, values)
        if not rows:
            raise NotFoundError(f"{self.label} not found.")
        return rows[0]

    def update_where(self, user_id: str, filters: Filters, values: dict) -> list[dict]:
        return self.db.update(self.table, {"user_id": user_id, **filters}, values)

    def delete(self, user_id: str, id_: str) -> None:
        if not self.db.delete(self.table, {"id": id_, "user_id": user_id}):
            raise NotFoundError(f"{self.label} not found.")

    def delete_where(self, user_id: str, filters: Filters) -> list[dict]:
        return self.db.delete(self.table, {"user_id": user_id, **filters})

    def count(self, user_id: str, filters: Filters | None = None) -> int:
        return self.db.count(self.table, {"user_id": user_id, **(filters or {})})


class ProfileRepo:
    def __init__(self, db: Gateway):
        self.db = db

    def get(self, user_id: str) -> dict | None:
        rows = self.db.select("profiles", {"id": user_id}, limit=1)
        return rows[0] if rows else None

    def upsert_name(self, user_id: str, display_name: str) -> dict:
        rows = self.db.update("profiles", {"id": user_id}, {"display_name": display_name})
        if rows:
            return rows[0]
        return self.db.insert("profiles", [{"id": user_id, "display_name": display_name}])[0]


def _repo(table: str, label: str, order: Order | None = Order("created_at", desc=True)) -> type[TableRepo]:
    return type(f"{label.replace(' ', '')}Repo", (TableRepo,), {"table": table, "label": label, "default_order": order})


WorkspaceRepo = _repo("workspaces", "Workspace")
DocumentRepo = _repo("documents", "Document")
ChunkRepo = _repo("document_chunks", "Chunk", Order("chunk_index"))
SummaryRepo = _repo("document_summaries", "Summary")
ConversationRepo = _repo("conversations", "Conversation", Order("updated_at", desc=True))
MessageRepo = _repo("messages", "Message", Order("created_at"))
CitationRepo = _repo("message_citations", "Citation", Order("rank"))
QuizSetRepo = _repo("quiz_sets", "Quiz")
QuizQuestionRepo = _repo("quiz_questions", "Question", Order("position"))
QuizAttemptRepo = _repo("quiz_attempts", "Quiz attempt", Order("started_at", desc=True))
QuizAnswerRepo = _repo("quiz_answers", "Answer", None)
FlashcardSetRepo = _repo("flashcard_sets", "Flashcard set")
FlashcardRepo = _repo("flashcards", "Flashcard", Order("position"))
FlashcardReviewRepo = _repo("flashcard_reviews", "Review", Order("reviewed_at", desc=True))
ActivityRepo = _repo("study_activities", "Activity")
UsageRepo = _repo("ai_usage_events", "Usage event")
