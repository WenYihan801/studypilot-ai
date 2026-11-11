from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from app.api.deps import Ctx
from app.core.config import Settings
from app.core.errors import ConflictError, ValidationFailedError
from app.db.gateway import Gateway, Storage, gte
from app.parsers import ParseError, detect_file_type, kind_from_mime, parse_document
from app.providers.base import AIProvider
from app.repositories import ChunkRepo, DocumentRepo, WorkspaceRepo
from app.services.chunking import chunk_sections
from app.services.usage import (
    EMBED_OPERATION,
    ActivityService,
    UsageService,
    utc_midnight,
)

logger = logging.getLogger("studypilot.documents")

PUBLIC_COLUMNS = (
    "id,workspace_id,filename,mime_type,size_bytes,sha256,status,page_count,chunk_count,"
    "error_message,processing_started_at,created_at"
)


def safe_filename(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return (name or "document")[:150]


class DocumentService:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.repo = DocumentRepo(ctx.db)
        self.workspaces = WorkspaceRepo(ctx.db)

    def list(self, workspace_id: str) -> list[dict]:
        self.workspaces.get(self.ctx.user_id, workspace_id)
        return self.repo.list(self.ctx.user_id, {"workspace_id": workspace_id}, columns=PUBLIC_COLUMNS)

    def get(self, document_id: str) -> dict:
        return self.repo.get(self.ctx.user_id, document_id, columns=PUBLIC_COLUMNS)

    def upload(self, workspace_id: str, filename: str, declared_mime: str | None, data: bytes) -> dict:
        s = self.ctx.settings
        uid = self.ctx.user_id
        self.workspaces.get(uid, workspace_id)
        if not data:
            raise ValidationFailedError("The file is empty.", code="empty_file")
        if len(data) > s.max_upload_bytes:
            raise ValidationFailedError(f"File exceeds the {s.max_upload_mb} MB limit.", code="file_too_large")
        if self.repo.count(uid, {"created_at": gte(utc_midnight().isoformat())}) >= s.daily_upload_limit:
            raise ValidationFailedError(f"Daily upload limit of {s.daily_upload_limit} files reached.", code="upload_limit")

        kind, mime = detect_file_type(filename, data, declared_mime)
        sha = hashlib.sha256(data).hexdigest()
        existing = self.repo.list(uid, {"workspace_id": workspace_id, "sha256": sha}, columns="id,filename")
        if existing:
            raise ConflictError(f"This file was already uploaded as '{existing[0]['filename']}'.", code="duplicate_file")

        doc_id = str(uuid.uuid4())
        name = safe_filename(filename)
        path = f"{uid}/{workspace_id}/{doc_id}/{name}"
        self.ctx.storage.upload(path, data, mime)
        try:
            doc = self.repo.create(
                uid,
                {
                    "id": doc_id,
                    "workspace_id": workspace_id,
                    "filename": name,
                    "storage_path": path,
                    "mime_type": mime,
                    "size_bytes": len(data),
                    "sha256": sha,
                    "status": "UPLOADED",
                },
            )
        except Exception:
            self.ctx.storage.remove([path])  # keep storage and DB consistent
            raise
        ActivityService(self.ctx.admin).log(uid, workspace_id, "document_uploaded", f"Uploaded {name} ({kind})")
        return {k: doc.get(k) for k in PUBLIC_COLUMNS.split(",")}

    def ensure_can_process(self, document_id: str) -> dict:
        doc = self.repo.get(self.ctx.user_id, document_id)
        if doc["status"] == "PROCESSING" and doc.get("processing_started_at"):
            started = datetime.fromisoformat(str(doc["processing_started_at"]))
            if datetime.now(UTC) - started < timedelta(minutes=self.ctx.settings.stale_processing_minutes):
                raise ConflictError("This document is already being processed.", code="already_processing")
        return doc

    def delete(self, document_id: str) -> None:
        doc = self.repo.get(self.ctx.user_id, document_id)
        self.ctx.storage.remove([doc["storage_path"]])
        self.repo.delete(self.ctx.user_id, document_id)  # chunks, vectors, summary cascade


class IngestionService:
    """Runs after the upload response is sent (FastAPI BackgroundTasks).

    Uses the admin client because the request (and its JWT) may be gone by the time it runs;
    every query is filtered by the document owner's user_id explicitly.
    """

    def __init__(self, admin: Gateway, storage: Storage, ai: AIProvider, settings: Settings):
        self.admin, self.storage, self.ai, self.settings = admin, storage, ai, settings
        self.docs = DocumentRepo(admin)
        self.chunks = ChunkRepo(admin)

    def _fail(self, user_id: str, doc_id: str, message: str) -> None:
        self.docs.update(user_id, doc_id, {"status": "FAILED", "error_message": message[:500]})

    def process(self, user_id: str, document_id: str) -> None:
        doc = self.docs.find(user_id, document_id)
        if not doc:
            return
        self.docs.update(
            user_id,
            document_id,
            {
                "status": "PROCESSING",
                "error_message": None,
                "processing_started_at": datetime.now(UTC).isoformat(),
            },
        )
        try:
            self.chunks.delete_where(user_id, {"document_id": document_id})  # idempotent re-processing
            if self._reuse_embeddings(user_id, doc):
                return
            data = self.storage.download(doc["storage_path"])
            parsed = parse_document(kind_from_mime(doc["mime_type"]), data)
            pieces = chunk_sections(parsed.sections, self.settings.chunk_size_tokens, self.settings.chunk_overlap_tokens)
            if not pieces:
                raise ParseError("No text could be extracted from this document.")
            result = self.ai.embed_texts([p.content for p in pieces], task="document")
            UsageService(self.admin, self.settings).record(user_id, self.ai.name, EMBED_OPERATION, result.usage)
            rows = [
                {
                    "document_id": document_id,
                    "workspace_id": doc["workspace_id"],
                    "chunk_index": p.index,
                    "content": p.content,
                    "page_number": p.page_number,
                    "section_title": p.section_title,
                    "embedding": vec,
                }
                for p, vec in zip(pieces, result.vectors, strict=True)
            ]
            for i in range(0, len(rows), 100):
                self.chunks.create_many(user_id, rows[i : i + 100])
            self.docs.update(
                user_id,
                document_id,
                {
                    "status": "READY",
                    "page_count": parsed.page_count,
                    "chunk_count": len(rows),
                    "error_message": None,
                },
            )
        except ParseError as exc:
            self._fail(user_id, document_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - any failure must surface as FAILED, never stuck PROCESSING
            logger.exception("Processing failed for document %s", document_id)
            message = getattr(exc, "message", None) or "Unexpected processing error. Try 'Reprocess'."
            self._fail(user_id, document_id, message)

    def _reuse_embeddings(self, user_id: str, doc: dict) -> bool:
        """Same file already processed in another workspace: copy its chunks instead of paying for embeddings again."""
        sources = [d for d in self.docs.list(user_id, {"sha256": doc["sha256"], "status": "READY"}) if d["id"] != doc["id"]]
        if not sources:
            return False
        src = sources[0]
        old = self.chunks.list(user_id, {"document_id": src["id"]})
        if not old:
            return False
        rows = [
            {
                "document_id": doc["id"],
                "workspace_id": doc["workspace_id"],
                "chunk_index": c["chunk_index"],
                "content": c["content"],
                "page_number": c["page_number"],
                "section_title": c["section_title"],
                "embedding": c["embedding"],
            }
            for c in old
        ]
        for i in range(0, len(rows), 100):
            self.chunks.create_many(user_id, rows[i : i + 100])
        self.docs.update(
            user_id,
            doc["id"],
            {
                "status": "READY",
                "page_count": src["page_count"],
                "chunk_count": len(rows),
                "error_message": None,
            },
        )
        return True
