"""Dependency wiring: who the user is, which DB client to use, which AI provider."""

from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.core.security import CurrentUser, get_current_user
from app.db.gateway import Gateway, Storage
from app.db.memory_gateway import MemoryGateway, MemoryStorage
from app.providers import build_provider
from app.providers.base import AIProvider

# Shared in-process store for DATA_BACKEND=memory (tests only).
memory_db = MemoryGateway()
memory_storage = MemoryStorage()


@lru_cache
def _admin_supabase(url: str, key: str):
    from app.db.supabase_gateway import SupabaseGateway

    return SupabaseGateway.admin(url, key)


def get_admin_db(settings: Settings = Depends(get_settings)) -> Gateway:
    if settings.data_backend == "memory":
        return memory_db
    return _admin_supabase(settings.supabase_url, settings.supabase_secret_key)


def get_storage(settings: Settings = Depends(get_settings)) -> Storage:
    if settings.data_backend == "memory":
        return memory_storage
    from app.db.supabase_gateway import SupabaseStorage

    return SupabaseStorage(_admin_supabase(settings.supabase_url, settings.supabase_secret_key).client, settings.storage_bucket)


def get_user_db(user: CurrentUser = Depends(get_current_user), settings: Settings = Depends(get_settings)) -> Gateway:
    if settings.data_backend == "memory":
        return memory_db
    from app.db.supabase_gateway import SupabaseGateway

    return SupabaseGateway.for_user(settings.supabase_url, settings.supabase_publishable_key, user.access_token)


_provider_cache: dict[str, AIProvider] = {}


def get_ai(settings: Settings = Depends(get_settings)) -> AIProvider:
    key = f"{settings.ai_provider}:{settings.gemini_chat_model}:{settings.gemini_quiz_model}"
    if key not in _provider_cache:
        _provider_cache[key] = build_provider(settings)
    return _provider_cache[key]


@dataclass
class Ctx:
    user: CurrentUser
    db: Gateway  # user-scoped: RLS enforced by Postgres
    admin: Gateway  # secret key: integrity tables + background jobs only
    storage: Storage
    ai: AIProvider
    settings: Settings

    @property
    def user_id(self) -> str:
        return self.user.id


def get_ctx(
    user: CurrentUser = Depends(get_current_user),
    db: Gateway = Depends(get_user_db),
    admin: Gateway = Depends(get_admin_db),
    storage: Storage = Depends(get_storage),
    ai: AIProvider = Depends(get_ai),
    settings: Settings = Depends(get_settings),
) -> Ctx:
    limiter.check(f"all:{user.id}", settings.rate_limit_per_minute)
    return Ctx(user=user, db=db, admin=admin, storage=storage, ai=ai, settings=settings)


def get_ai_ctx(ctx: Ctx = Depends(get_ctx)) -> Ctx:
    """For endpoints that call the LLM: stricter per-minute limit."""
    limiter.check(f"ai:{ctx.user_id}", ctx.settings.ai_rate_limit_per_minute)
    return ctx
