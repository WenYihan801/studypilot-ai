from app.api.deps import Ctx
from app.providers.base import EmbedResult
from app.services.usage import UsageService


class RetrievalService:
    """Query embedding + pgvector search, always scoped to (user_id, workspace_id)."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    def search(
        self, workspace_id: str, query: str, *, top_k: int | None = None, document_ids: list[str] | None = None
    ) -> list[dict]:
        emb: EmbedResult = self.ctx.ai.embed_texts([query], task="query")
        UsageService(self.ctx.admin, self.ctx.settings).record(self.ctx.user_id, self.ctx.ai.name, "embed_query", emb.usage)
        rows = self.ctx.db.rpc(
            "match_chunks",
            {
                "query_embedding": emb.vectors[0],
                "p_workspace_id": workspace_id,
                "p_user_id": self.ctx.user_id,
                "match_count": top_k or self.ctx.settings.retrieval_top_k,
                "p_document_ids": document_ids or None,
            },
        )
        min_score = self.ctx.settings.retrieval_min_score
        return [r for r in rows if (r.get("similarity") or 0) >= min_score]
