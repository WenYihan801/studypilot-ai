"""Gemini implementation using the official `google-genai` SDK."""

import logging
import time

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AIProviderError
from app.providers.base import (
    AIProvider,
    EmbedResult,
    EmbedTask,
    ModelRole,
    StructuredResult,
    T,
    TextResult,
    Usage,
    l2_normalize,
)

logger = logging.getLogger("studypilot.gemini")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
EMBED_BATCH_SIZE = 50


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (or use AI_PROVIDER=mock).")
        self._s = settings
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(settings.ai_timeout_seconds * 1000)),
        )

    # ------------------------------------------------------------------ helpers
    def _thinking(self):
        level = self._s.gemini_thinking_level.strip().upper()
        return types.ThinkingConfig(thinking_level=level) if level else None

    def _model(self, role: ModelRole) -> str:
        return self._s.gemini_quiz_model if role == "quiz" else self._s.gemini_chat_model

    def _call(self, fn, *args, **kwargs):
        """Limited retry with exponential backoff on transient errors. Never loops forever."""
        attempts = self._s.ai_max_retries + 1
        for attempt in range(attempts):
            try:
                return fn(*args, **kwargs)
            except errors.APIError as exc:
                retryable = exc.code in RETRYABLE_STATUS
                logger.warning("Gemini API error %s (attempt %d/%d)", exc.code, attempt + 1, attempts)
                if not retryable or attempt == attempts - 1:
                    if exc.code == 429:
                        raise AIProviderError(
                            "The AI provider's rate limit or free quota was reached. Try again later.",
                            code="ai_rate_limited",
                            status_code=503,
                        ) from exc
                    raise AIProviderError("The AI provider returned an error.") from exc
                time.sleep(min(2**attempt, 8))
        raise AIProviderError("The AI provider is unavailable.")  # pragma: no cover

    @staticmethod
    def _usage(model: str, response) -> Usage:
        meta = getattr(response, "usage_metadata", None)
        return Usage(
            model=model,
            input_tokens=(meta.prompt_token_count or 0) if meta else 0,
            output_tokens=((meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)) if meta else 0,
        )

    # ------------------------------------------------------------------ interface
    def generate_text(self, prompt, *, system=None, role="chat", max_output_tokens=1024, temperature=0.3):
        model = self._model(role)
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            thinking_config=self._thinking(),
        )
        resp = self._call(self._client.models.generate_content, model=model, contents=prompt, config=config)
        text = resp.text or ""
        if not text.strip():
            raise AIProviderError("The AI provider returned an empty response.")
        return TextResult(text=text, usage=self._usage(model, resp))

    def generate_structured_output(
        self, prompt, schema: type[T], *, system=None, role="chat", max_output_tokens=2048, temperature=0.2
    ) -> StructuredResult[T]:
        model = self._model(role)
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            thinking_config=self._thinking(),
        )
        resp = self._call(self._client.models.generate_content, model=model, contents=prompt, config=config)
        raw = resp.text or ""
        try:
            # Never trust the model: always re-validate with our own Pydantic schema.
            data = schema.model_validate_json(raw)
        except ValidationError as exc:
            logger.warning("Structured output failed validation for %s", schema.__name__)
            raise AIProviderError("The AI returned data in an unexpected format.", code="ai_invalid_output") from exc
        return StructuredResult(data=data, usage=self._usage(model, resp))

    def embed_texts(self, texts: list[str], *, task: EmbedTask) -> EmbedResult:
        model = self._s.gemini_embedding_model
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        vectors: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            resp = self._call(
                self._client.models.embed_content,
                model=model,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self._s.embedding_dim),
            )
            for emb in resp.embeddings or []:
                values = list(emb.values or [])
                if len(values) != self._s.embedding_dim:
                    raise AIProviderError(f"Embedding dimension mismatch: expected {self._s.embedding_dim}, got {len(values)}.")
                # gemini-embedding-001 only normalises full 3072-dim output; truncated output must be normalised.
                vectors.append(l2_normalize(values))
        if len(vectors) != len(texts):
            raise AIProviderError("Embedding count mismatch from AI provider.")
        # Approximate token count (the embed endpoint does not always report usage).
        approx_tokens = sum(len(t) for t in texts) // 4
        return EmbedResult(vectors=vectors, usage=Usage(model=model, input_tokens=approx_tokens))
