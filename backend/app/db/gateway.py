"""A deliberately small data-access interface.

Repositories talk to this interface, never to supabase-py directly. Two implementations:
- SupabaseGateway: PostgREST with either the *user's* JWT (RLS enforced) or the secret key (admin).
- MemoryGateway:   in-process dicts, used by the automated test-suite (no network, no cloud).
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

OpName = Literal["eq", "neq", "in", "gte", "lte", "gt", "lt", "is_null", "not_null"]


@dataclass(frozen=True)
class Op:
    op: OpName
    value: Any = None


def gte(v: Any) -> Op:
    return Op("gte", v)


def lt(v: Any) -> Op:
    return Op("lt", v)


def neq(v: Any) -> Op:
    return Op("neq", v)


def in_(values: list[Any]) -> Op:
    return Op("in", list(values))


Filters = dict[str, Any]  # column -> plain value (eq) or Op


@dataclass(frozen=True)
class Order:
    column: str
    desc: bool = False


class Gateway(Protocol):
    def select(
        self,
        table: str,
        filters: Filters | None = None,
        *,
        columns: str = "*",
        order: Order | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...

    def insert(self, table: str, rows: list[dict]) -> list[dict]: ...

    def update(self, table: str, filters: Filters, values: dict) -> list[dict]: ...

    def delete(self, table: str, filters: Filters) -> list[dict]: ...

    def count(self, table: str, filters: Filters | None = None) -> int: ...

    def rpc(self, name: str, params: dict) -> list[dict]: ...


class Storage(Protocol):
    def upload(self, path: str, data: bytes, content_type: str) -> None: ...

    def download(self, path: str) -> bytes: ...

    def remove(self, paths: list[str]) -> None: ...
