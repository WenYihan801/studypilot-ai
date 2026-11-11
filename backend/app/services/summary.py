from app.api.deps import Ctx
from app.core.errors import ValidationFailedError
from app.repositories import ChunkRepo, DocumentRepo, SummaryRepo
from app.schemas.ai import SummaryDraft
from app.services.context import CHUNK_COLUMNS
from app.services.prompts import (
    SUMMARY_FINAL_SYSTEM,
    SUMMARY_PART_SYSTEM,
    format_sources,
    summary_final_prompt,
)
from app.services.usage import ActivityService, UsageService

MAX_GROUP_CHARS = 12000


def _page_label(chunks: list[dict]) -> str | None:
    pages = sorted({c["page_number"] for c in chunks if c.get("page_number")})
    if not pages:
        titles = [c["section_title"] for c in chunks if c.get("section_title")]
        return f"Section: {titles[0]}" if titles else None
    return f"p. {pages[0]}" if len(pages) == 1 else f"pp. {pages[0]}–{pages[-1]}"


class SummaryService:
    """Map-reduce summary: summarise groups of chunks, then combine. Never sends a whole long document at once."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.cache = SummaryRepo(ctx.db)

    def get_cached(self, document_id: str) -> dict | None:
        DocumentRepo(self.ctx.db).get(self.ctx.user_id, document_id)
        rows = self.cache.list(self.ctx.user_id, {"document_id": document_id}, limit=1)
        return self._out(rows[0], cached=True) if rows else None

    def generate(self, document_id: str, force: bool = False) -> dict:
        uid, s = self.ctx.user_id, self.ctx.settings
        doc = DocumentRepo(self.ctx.db).get(uid, document_id)
        if doc["status"] != "READY":
            raise ValidationFailedError("Document is not processed yet.", code="document_not_ready")
        if not force and (cached := self.get_cached(document_id)):
            return cached
        usage = UsageService(self.ctx.admin, s)
        usage.check_quota(uid)

        chunks = ChunkRepo(self.ctx.db).list(uid, {"document_id": document_id}, columns=CHUNK_COLUMNS)
        chunks = [{**c, "filename": doc["filename"]} for c in chunks]
        total = sum(len(c["content"]) for c in chunks)
        group_chars = max(MAX_GROUP_CHARS, total // s.max_summary_groups + 1)
        groups: list[list[dict]] = [[]]
        for c in chunks:
            if groups[-1] and sum(len(x["content"]) for x in groups[-1]) + len(c["content"]) > group_chars:
                groups.append([])
            groups[-1].append(c)

        parts, references = [], []
        for g in groups:
            block, _ = format_sources(g)
            res = self.ctx.ai.generate_text(block, system=SUMMARY_PART_SYSTEM, max_output_tokens=800)
            usage.record(uid, self.ctx.ai.name, "summary_part", res.usage)
            parts.append(res.text)
            references.append({"filename": doc["filename"], "location": _page_label(g), "chunk_ids": [c["id"] for c in g][:20]})
        final = self.ctx.ai.generate_structured_output(
            summary_final_prompt(doc["filename"], parts), SummaryDraft, system=SUMMARY_FINAL_SYSTEM, max_output_tokens=2500
        )
        usage.record(uid, self.ctx.ai.name, "summary", final.usage)

        content = {**final.data.model_dump(), "source_references": references}
        self.cache.delete_where(uid, {"document_id": document_id})
        row = self.cache.create(uid, {"document_id": document_id, "content_json": content, "model_name": final.usage.model})
        ActivityService(self.ctx.admin).log(uid, doc["workspace_id"], "summary", f"Summarised {doc['filename']}")
        return self._out(row, cached=False)

    @staticmethod
    def _out(row: dict, cached: bool) -> dict:
        return {
            "document_id": row["document_id"],
            "summary": row["content_json"],
            "model_name": row.get("model_name"),
            "created_at": row["created_at"],
            "cached": cached,
        }
