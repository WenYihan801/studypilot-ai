from typing import Any

from supabase import Client, create_client

from app.db.gateway import Filters, Op, Order


def _apply_filters(query: Any, filters: Filters | None) -> Any:
    for column, value in (filters or {}).items():
        op = value if isinstance(value, Op) else Op("eq", value)
        if op.op == "eq":
            query = query.eq(column, op.value)
        elif op.op == "neq":
            query = query.neq(column, op.value)
        elif op.op == "in":
            query = query.in_(column, op.value)
        elif op.op == "gte":
            query = query.gte(column, op.value)
        elif op.op == "lte":
            query = query.lte(column, op.value)
        elif op.op == "gt":
            query = query.gt(column, op.value)
        elif op.op == "lt":
            query = query.lt(column, op.value)
        elif op.op == "is_null":
            query = query.is_(column, "null")
        elif op.op == "not_null":
            query = query.not_.is_(column, "null")
        else:  # pragma: no cover
            raise ValueError(f"Unsupported operator {op.op}")
    return query


class SupabaseGateway:
    def __init__(self, client: Client):
        self._client = client

    @classmethod
    def for_user(cls, url: str, publishable_key: str, access_token: str) -> "SupabaseGateway":
        """PostgREST requests carry the user's JWT, so Postgres RLS policies apply."""
        client = create_client(url, publishable_key)
        client.postgrest.auth(access_token)
        return cls(client)

    @classmethod
    def admin(cls, url: str, secret_key: str) -> "SupabaseGateway":
        """Bypasses RLS. Only used for integrity tables and background jobs, always with explicit user_id filters."""
        return cls(create_client(url, secret_key))

    @property
    def client(self) -> Client:
        return self._client

    def select(
        self,
        table: str,
        filters: Filters | None = None,
        *,
        columns: str = "*",
        order: Order | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        q = _apply_filters(self._client.table(table).select(columns), filters)
        if order:
            q = q.order(order.column, desc=order.desc)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []

    def insert(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        return self._client.table(table).insert(rows).execute().data or []

    def update(self, table: str, filters: Filters, values: dict) -> list[dict]:
        if not filters:
            raise ValueError("Refusing to update without filters")
        q = _apply_filters(self._client.table(table).update(values), filters)
        return q.execute().data or []

    def delete(self, table: str, filters: Filters) -> list[dict]:
        if not filters:
            raise ValueError("Refusing to delete without filters")
        q = _apply_filters(self._client.table(table).delete(), filters)
        return q.execute().data or []

    def count(self, table: str, filters: Filters | None = None) -> int:
        q = _apply_filters(self._client.table(table).select("id", count="exact", head=True), filters)
        return q.execute().count or 0

    def rpc(self, name: str, params: dict) -> list[dict]:
        return self._client.rpc(name, params).execute().data or []


class SupabaseStorage:
    """Storage is accessed with the secret key; the backend enforces the {user_id}/... path prefix."""

    def __init__(self, client: Client, bucket: str):
        self._bucket = client.storage.from_(bucket)

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self._bucket.upload(path, data, {"content-type": content_type, "upsert": "false"})

    def download(self, path: str) -> bytes:
        return self._bucket.download(path)

    def remove(self, paths: list[str]) -> None:
        # Storage API accepts batches; keep them modest.
        for i in range(0, len(paths), 100):
            self._bucket.remove(paths[i : i + 100])
