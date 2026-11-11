from app.core.config import Settings
from app.providers.base import AIProvider


def build_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "gemini":
        from app.providers.gemini import GeminiProvider

        return GeminiProvider(settings)
    from app.providers.mock import MockProvider

    return MockProvider(settings)
