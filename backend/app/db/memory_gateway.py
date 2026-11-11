"""In-memory implementation of the Gateway, mirroring the SQL schema's cascades and unique keys.

Used only by tests (DATA_BACKEND=memory). It intentionally behaves like the "admin" client
(no RLS); isolation in tests is therefore proven at the application layer, and RLS itself is
proven against a real Supabase project by tests/integration/test_rls_live.py.
"""

import copy
import math
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.errors import ConflictError
from app.db.gateway import Filters, Op, Order

# parent table -> list of (child table, foreign-key column, action)
CASCADES: dict[str, list[tuple[str, str, str]]] = {
    "workspaces": [
        ("documents", "workspace_id", "cascade"),
        ("document_chunks", "workspace_id", "cascade"),
        ("conversations", "workspace_id", "cascade"),
        ("quiz_sets", "workspace_id", "cascade"),
        ("flashcard_sets", "workspace_id", "cascade"),
        ("flashcards", "workspace_id", "cascade"),
        ("study_activities", "workspace_id", "cascade"),
    ],
    "documents": [
        ("document_chunks", "document_id", "cascade"),
        ("document_summaries", "document_id", "cascade"),
    ],
    "document_chunks": [
        ("message_citations", "chunk_id", "cascade"),
        ("flashcards", "source_chunk_id", "set_null"),
    ],
    "conversations": [("messages", "conversation_id", "cascade")],
    "messages": [("message_citations", "message_id", "cascade")],
    "quiz_sets": [("quiz_questions", "quiz_set_id", "cascade"), ("quiz_attempts", "quiz_set_id", "cascade")],
    "quiz_attempts": [("quiz_answers", "attempt_id", "cascade")],
    "quiz_questions": [("quiz_answers", "question_id", "cascade")],
    "flashcard_sets": [("flashcards", "set_id", "cascade")],
    "flashcards": [("flashcard_reviews", "flashcard_id", "cascade")],
}

UNIQUE: dict[str, list[tuple[str, ...]]] = {
    "documents": [("workspace_id", "sha256")],
    "document_chunks": [("document_id", "chunk_index")],
    "document_summaries": [("document_id",)],
    "quiz_answers": [("attempt_id", "question_id")],
}

DEFAULTS: dict[str, dict[str, Any]] = {
    "documents": {
        "status": "UPLOADED",
        "chunk_count": 0,
        "page_count": None,
        "error_message": None,
        "processing_started_at": None,
    },
    "workspaces": {"description": ""},
    "flashcards": {"mastery_status": "NEW", "reviewed_at": None, "source_chunk_id": None, "position": 0},
    "messages": {"insufficient_evidence": False, "model_name": None, "input_tokens": None, "output_tokens": None},
    "quiz_attempts": {"score": None, "submitted_at": None},
    "quiz_answers": {"feedback": ""},
}

TIMESTAMP_COLUMN = {
    "quiz_attempts": "started_at",
    "flashcard_reviews": "reviewed_at",
    "quiz_questions": None,
    "quiz_answers": None,
    "message_citations": None,
    "flashcards": None,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _matches(row: dict, filters: Filters | None) -> bool:
    for column, value in (filters or {}).items():
        op = value if isinstance(value, Op) else Op("eq", value)
        cell = row.get(column)
        if op.op == "eq" and cell != op.value:
            return False
        if op.op == "neq" and cell == op.value:
            return False
        if op.op == "in" and cell not in op.value:
            return False
        if op.op == "is_null" and cell is not None:
            return False
        if op.op == "not_null" and cell is None:
            return False
        if op.op in ("gte", "lte", "gt", "lt"):
            if cell is None:
                return False
            if op.op == "gte" and not cell >= op.value:
                return False
            if op.op == "lte" and not cell <= op.value:
                return False
            if op.op == "gt" and not cell > op.value:
                return False
            if op.op == "lt" and not cell < op.value:
                return False
    return True


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class MemoryGateway:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self.tables.clear()

    def _rows(self, table: str) -> list[dict]:
        return self.tables.setdefault(table, [])

    def select(self, table, filters=None, *, columns="*", order: Order | None = None, limit=None):
        with self._lock:
            rows = [copy.deepcopy(r) for r in self._rows(table) if _matches(r, filters)]
        if order:
            rows.sort(key=lambda r: (r.get(order.column) is None, r.get(order.column)), reverse=order.desc)
        return rows[:limit] if limit else rows

    def insert(self, table, rows):
        out = []
        with self._lock:
            for row in rows:
                new = {**DEFAULTS.get(table, {}), **copy.deepcopy(row)}
                new.setdefault("id", str(uuid.uuid4()))
                ts_col = TIMESTAMP_COLUMN.get(table, "created_at")
                if ts_col:
                    new.setdefault(ts_col, _now())
                if table in ("workspaces", "conversations"):
                    new.setdefault("updated_at", new["created_at"])
                for key in UNIQUE.get(table, []):
                    for existing in self._rows(table):
                        if all(existing.get(k) == new.get(k) for k in key):
                            raise ConflictError(f"Duplicate value for {table}{key}")
                self._rows(table).append(new)
                out.append(copy.deepcopy(new))
        return out

    def update(self, table, filters, values):
        if not filters:
            raise ValueError("Refusing to update without filters")
        out = []
        with self._lock:
            for row in self._rows(table):
                if _matches(row, filters):
                    row.update(copy.deepcopy(values))
                    if table in ("workspaces", "conversations"):
                        row["updated_at"] = _now()
                    out.append(copy.deepcopy(row))
        return out

    def delete(self, table, filters):
        if not filters:
            raise ValueError("Refusing to delete without filters")
        with self._lock:
            return self._delete_where(table, lambda r: _matches(r, filters))

    def _delete_where(self, table: str, pred) -> list[dict]:
        rows = self._rows(table)
        removed = [r for r in rows if pred(r)]
        self.tables[table] = [r for r in rows if not pred(r)]
        ids = {r["id"] for r in removed}
        for child, fk, action in CASCADES.get(table, []):
            if action == "cascade":
                self._delete_where(child, lambda r, fk=fk: r.get(fk) in ids)
            else:
                for r in self._rows(child):
                    if r.get(fk) in ids:
                        r[fk] = None
        return [copy.deepcopy(r) for r in removed]

    def count(self, table, filters=None):
        with self._lock:
            return sum(1 for r in self._rows(table) if _matches(r, filters))

    def rpc(self, name: str, params: dict) -> list[dict]:
        if name != "match_chunks":
            raise ValueError(f"Unknown rpc {name}")
        with self._lock:
            docs = {d["id"]: d for d in self._rows("documents")}
            doc_filter = params.get("p_document_ids")
            scored = []
            for c in self._rows("document_chunks"):
                d = docs.get(c["document_id"])
                if (
                    c["workspace_id"] != params["p_workspace_id"]
                    or c["user_id"] != params["p_user_id"]
                    or not d
                    or d["status"] != "READY"
                    or (doc_filter and c["document_id"] not in doc_filter)
                ):
                    continue
                scored.append(
                    {
                        "id": c["id"],
                        "document_id": c["document_id"],
                        "chunk_index": c["chunk_index"],
                        "content": c["content"],
                        "page_number": c.get("page_number"),
                        "section_title": c.get("section_title"),
                        "filename": d["filename"],
                        "similarity": _cosine(params["query_embedding"], c["embedding"]),
                    }
                )
        scored.sort(key=lambda r: r["similarity"], reverse=True)
        return scored[: max(1, min(params.get("match_count", 5), 20))]


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        if path in self.objects:
            raise ConflictError("Storage object already exists")
        self.objects[path] = data

    def download(self, path: str) -> bytes:
        return self.objects[path]

    def remove(self, paths: list[str]) -> None:
        for p in paths:
            self.objects.pop(p, None)
