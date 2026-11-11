from functools import lru_cache
from typing import Literal

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or backend/.env in development)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _strip_whitespace(cls, v):
        # Values pasted into dashboards (Render, Vercel) often carry a stray space or newline.
        # An untrimmed key ends up in an HTTP header and makes Supabase reset the HTTP/2 stream.
        return v.strip() if isinstance(v, str) else v

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    # Comma-separated list, e.g. "http://localhost:5173,https://studypilot.vercel.app"
    cors_origins: str = "http://localhost:5173"

    # "supabase" in dev/prod; "memory" is an in-process store used by the automated tests.
    data_backend: Literal["supabase", "memory"] = "supabase"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    storage_bucket: str = "documents"

    # AI provider. Model IDs live here, never in business code.
    ai_provider: Literal["gemini", "mock"] = "mock"
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.1-flash-lite"
    gemini_quiz_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    # Gemini 3.x models think by default and thinking tokens count against max_output_tokens.
    # "low" keeps answers fast and cheap; set to "" to use the model default (needed for 2.5 models).
    gemini_thinking_level: str = "low"
    # Must match the vector(N) column in the migration.
    embedding_dim: int = 768
    ai_timeout_seconds: float = 60.0
    ai_max_retries: int = 2

    # RAG parameters (starting points; tune with backend/eval).
    chunk_size_tokens: int = 600
    chunk_overlap_tokens: int = 100
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.3

    # Limits
    max_upload_mb: int = 20
    max_question_chars: int = 2000
    max_answer_tokens: int = 1500
    max_quiz_questions: int = 20
    max_flashcards: int = 30
    max_summary_groups: int = 8
    daily_ai_request_limit: int = 100
    daily_upload_limit: int = 30
    rate_limit_per_minute: int = 60
    ai_rate_limit_per_minute: int = 10
    stale_processing_minutes: int = 10

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def supabase_jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_jwt_issuer}/.well-known/jwks.json"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def secret_values(self) -> list[str]:
        """Values that must never appear in logs."""
        return [v for v in (self.supabase_secret_key, self.gemini_api_key) if v]


@lru_cache
def get_settings() -> Settings:
    return Settings()
