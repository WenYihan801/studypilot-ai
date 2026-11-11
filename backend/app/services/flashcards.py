from datetime import UTC, datetime

from app.api.deps import Ctx
from app.core.errors import AIProviderError, ValidationFailedError
from app.db.gateway import in_, neq
from app.repositories import (
    ChunkRepo,
    DocumentRepo,
    FlashcardRepo,
    FlashcardReviewRepo,
    FlashcardSetRepo,
    WorkspaceRepo,
)
from app.schemas.ai import FlashcardDraft
from app.services.context import sample_chunks
from app.services.prompts import FLASHCARD_SYSTEM, flashcard_prompt, format_sources
from app.services.usage import ActivityService, UsageService

MASTERY = ("NEW", "LEARNING", "MASTERED")


class FlashcardService:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.sets = FlashcardSetRepo(ctx.db)
        self.cards = FlashcardRepo(ctx.db)
        self.reviews = FlashcardReviewRepo(ctx.db)

    def generate(self, workspace_id: str, *, title: str | None, count: int, document_ids: list[str] | None) -> dict:
        uid, s = self.ctx.user_id, self.ctx.settings
        WorkspaceRepo(self.ctx.db).get(uid, workspace_id)
        if not 1 <= count <= s.max_flashcards:
            raise ValidationFailedError(f"Card count must be between 1 and {s.max_flashcards}.")
        usage = UsageService(self.ctx.admin, s)
        usage.check_quota(uid)
        chunks = sample_chunks(self.ctx, workspace_id, document_ids, max_chunks=min(16, count + 4))
        block, label_map = format_sources(chunks)
        res = self.ctx.ai.generate_structured_output(
            flashcard_prompt(block, count),
            FlashcardDraft,
            system=FLASHCARD_SYSTEM,
            max_output_tokens=min(6000, 250 * count + 300),
        )
        usage.record(uid, self.ctx.ai.name, "flashcards_generate", res.usage)
        seen, valid = set(), []
        for c in res.data.cards:
            key = c.front.strip().lower()
            if c.source_label in label_map and key not in seen:
                seen.add(key)
                valid.append(c)
        valid = valid[:count]
        if not valid:
            raise AIProviderError("The AI did not produce any valid flashcards. Please try again.", code="ai_invalid_output")
        fs = self.sets.create(
            uid,
            {"workspace_id": workspace_id, "title": (title or "").strip() or f"Flashcards – {datetime.now(UTC):%d %b %Y %H:%M}"},
        )
        self.cards.create_many(
            uid,
            [
                {
                    "set_id": fs["id"],
                    "workspace_id": workspace_id,
                    "position": i,
                    "front": c.front.strip(),
                    "back": c.back.strip(),
                    "source_chunk_id": label_map[c.source_label]["id"],
                }
                for i, c in enumerate(valid)
            ],
        )
        ActivityService(self.ctx.admin).log(
            uid, workspace_id, "flashcards_generated", f"Generated {len(valid)} flashcards in '{fs['title']}'"
        )
        return self.get_set(fs["id"])

    def list_sets(self, workspace_id: str) -> list[dict]:
        WorkspaceRepo(self.ctx.db).get(self.ctx.user_id, workspace_id)
        sets = self.sets.list(self.ctx.user_id, {"workspace_id": workspace_id})
        cards = self.cards.list(self.ctx.user_id, {"workspace_id": workspace_id}, columns="id,set_id,mastery_status")
        out = []
        for fs in sets:
            mine = [c for c in cards if c["set_id"] == fs["id"]]
            out.append(
                {**fs, "card_count": len(mine), "mastered_count": sum(1 for c in mine if c["mastery_status"] == "MASTERED")}
            )
        return out

    def _decorate(self, cards: list[dict]) -> list[dict]:
        ids = [c["source_chunk_id"] for c in cards if c.get("source_chunk_id")]
        chunks = (
            {
                c["id"]: c
                for c in ChunkRepo(self.ctx.db).list(
                    self.ctx.user_id, {"id": in_(ids)}, columns="id,document_id,page_number,content"
                )
            }
            if ids
            else {}
        )
        doc_ids = list({c["document_id"] for c in chunks.values()})
        docs = (
            {
                d["id"]: d["filename"]
                for d in DocumentRepo(self.ctx.db).list(self.ctx.user_id, {"id": in_(doc_ids)}, columns="id,filename")
            }
            if doc_ids
            else {}
        )
        out = []
        for c in cards:
            ch = chunks.get(c.get("source_chunk_id"))
            out.append(
                {
                    **c,
                    "source": {
                        "chunk_id": ch["id"],
                        "filename": docs.get(ch["document_id"]),
                        "page_number": ch["page_number"],
                        "quote_text": ch["content"][:300],
                    }
                    if ch
                    else None,
                }
            )
        return out

    def get_set(self, set_id: str) -> dict:
        fs = self.sets.get(self.ctx.user_id, set_id)
        return {**fs, "cards": self._decorate(self.cards.list(self.ctx.user_id, {"set_id": set_id}))}

    def delete_set(self, set_id: str) -> None:
        self.sets.delete(self.ctx.user_id, set_id)

    def due(self, workspace_id: str | None = None) -> list[dict]:
        filters: dict = {"mastery_status": neq("MASTERED")}
        if workspace_id:
            WorkspaceRepo(self.ctx.db).get(self.ctx.user_id, workspace_id)
            filters["workspace_id"] = workspace_id
        return self._decorate(self.cards.list(self.ctx.user_id, filters, limit=200))

    def update_status(self, card_id: str, status: str) -> dict:
        if status not in MASTERY:
            raise ValidationFailedError("mastery_status must be NEW, LEARNING or MASTERED.")
        uid = self.ctx.user_id
        card = self.cards.get(uid, card_id)
        now = datetime.now(UTC).isoformat()
        updated = self.cards.update(uid, card_id, {"mastery_status": status, "reviewed_at": now})
        self.reviews.create(
            uid, {"flashcard_id": card_id, "previous_status": card["mastery_status"], "new_status": status, "reviewed_at": now}
        )
        ActivityService(self.ctx.admin).log(
            uid, card["workspace_id"], "flashcard_review", f"Marked a flashcard as {status.lower()}"
        )
        return self._decorate([updated])[0]

    def history(self, card_id: str) -> list[dict]:
        self.cards.get(self.ctx.user_id, card_id)
        return self.reviews.list(self.ctx.user_id, {"flashcard_id": card_id}, limit=100)
