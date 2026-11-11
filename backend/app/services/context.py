from app.api.deps import Ctx
from app.core.errors import ValidationFailedError
from app.db.gateway import in_
from app.repositories import ChunkRepo, DocumentRepo

CHUNK_COLUMNS = "id,document_id,chunk_index,content,page_number,section_title"


def ready_documents(ctx: Ctx, workspace_id: str, document_ids: list[str] | None) -> dict[str, dict]:
    filters: dict = {"workspace_id": workspace_id, "status": "READY"}
    if document_ids:
        filters["id"] = in_(document_ids)
    docs = DocumentRepo(ctx.db).list(ctx.user_id, filters, columns="id,filename")
    if not docs:
        raise ValidationFailedError(
            "No processed (READY) documents found. Upload a document and wait for processing.", code="no_ready_documents"
        )
    if document_ids and len(docs) != len(set(document_ids)):
        raise ValidationFailedError("Some selected documents are not in this workspace or not ready.")
    return {d["id"]: d for d in docs}


def sample_chunks(ctx: Ctx, workspace_id: str, document_ids: list[str] | None, max_chunks: int) -> list[dict]:
    """Evenly spread chunks across the selected documents so generated content covers the whole material."""
    docs = ready_documents(ctx, workspace_id, document_ids)
    chunks = ChunkRepo(ctx.db).list(ctx.user_id, {"document_id": in_(list(docs))}, columns=CHUNK_COLUMNS)
    chunks.sort(key=lambda c: (c["document_id"], c["chunk_index"]))
    if len(chunks) > max_chunks:
        step = len(chunks) / max_chunks
        chunks = [chunks[int(i * step)] for i in range(max_chunks)]
    return [{**c, "filename": docs[c["document_id"]]["filename"]} for c in chunks]
