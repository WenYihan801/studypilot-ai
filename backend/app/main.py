import logging
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _log_key_shapes(settings) -> None:
    """Log only the shape of configured keys (prefix type, length, charset OK) - never the value."""
    log = logging.getLogger("studypilot.config")
    for name in ("supabase_publishable_key", "supabase_secret_key", "gemini_api_key"):
        v = getattr(settings, name)
        if not v:
            continue
        kind = "sb_secret" if v.startswith("sb_secret_") else "sb_publishable" if v.startswith("sb_publishable_") else "other"
        log.info("config %s: kind=%s len=%d charset_ok=%s", name, kind, len(v), bool(_KEY_RE.match(v)))


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    _log_key_shapes(settings)
    app = FastAPI(
        title="StudyPilot AI API",
        version=__version__,
        description="Cloud-based AI Study & Research Assistant. All endpoints except /health require a Supabase JWT.",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    register_error_handlers(app)  # before CORS so CORS wraps the catch-all middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,  # explicit allowlist, never "*"
        allow_credentials=False,  # we use Authorization headers, not cookies
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    app.include_router(router)
    return app


app = create_app()
