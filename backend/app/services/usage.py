"""AI usage accounting and the per-user daily quota (persisted, survives restarts)."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.errors import QuotaExceededError
from app.db.gateway import Gateway, gte, neq
from app.providers.base import Usage
from app.repositories import ActivityRepo, UsageRepo

# Paid-tier list prices (USD per 1M tokens) from ai.google.dev/gemini-api/docs/pricing, checked 2026-11-11.
# Used for an *estimate* only. On the free tier the actual charge is $0. Update when prices change.
PRICES: dict[str, tuple[float, float]] = {
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-embedding-001": (0.15, 0.0),
}
EMBED_OPERATION = "embed_document"


def utc_midnight() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def estimate_cost(usage: Usage) -> float:
    inp, out = PRICES.get(usage.model, (0.0, 0.0))
    return round((usage.input_tokens * inp + usage.output_tokens * out) / 1_000_000, 6)


class UsageService:
    def __init__(self, admin: Gateway, settings: Settings):
        self.repo = UsageRepo(admin)
        self.settings = settings

    def requests_today(self, user_id: str) -> int:
        return self.repo.count(user_id, {"created_at": gte(utc_midnight().isoformat()), "operation": neq(EMBED_OPERATION)})

    def check_quota(self, user_id: str) -> None:
        if self.requests_today(user_id) >= self.settings.daily_ai_request_limit:
            raise QuotaExceededError(
                f"Daily AI limit of {self.settings.daily_ai_request_limit} requests reached. It resets at 00:00 UTC."
            )

    def record(self, user_id: str, provider: str, operation: str, usage: Usage) -> None:
        self.repo.create(
            user_id,
            {
                "provider": provider,
                "model": usage.model,
                "operation": operation,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "estimated_cost": estimate_cost(usage),
            },
        )

    def summary(self, user_id: str) -> dict:
        since = (utc_midnight() - timedelta(days=29)).isoformat()
        events = self.repo.list(user_id, {"created_at": gte(since)}, limit=5000)
        today = utc_midnight().isoformat()
        by_op: dict[str, dict] = defaultdict(lambda: {"requests": 0, "input_tokens": 0, "output_tokens": 0})
        by_day: dict[str, int] = defaultdict(int)
        for e in events:
            agg = by_op[e["operation"]]
            agg["requests"] += 1
            agg["input_tokens"] += e["input_tokens"] or 0
            agg["output_tokens"] += e["output_tokens"] or 0
            by_day[str(e["created_at"])[:10]] += 1
        today_events = [e for e in events if str(e["created_at"]) >= today]
        return {
            "requests_today": self.requests_today(user_id),
            "daily_limit": self.settings.daily_ai_request_limit,
            "tokens_today": sum((e["input_tokens"] or 0) + (e["output_tokens"] or 0) for e in today_events),
            "estimated_cost_30d": round(sum(float(e["estimated_cost"] or 0) for e in events), 4),
            "by_operation": [{"operation": k, **v} for k, v in sorted(by_op.items())],
            "by_day": [{"date": k, "requests": v} for k, v in sorted(by_day.items())],
            "provider": self.settings.ai_provider,
        }


class ActivityService:
    def __init__(self, admin: Gateway):
        self.repo = ActivityRepo(admin)

    def log(self, user_id: str, workspace_id: str | None, activity_type: str, description: str) -> None:
        self.repo.create(
            user_id, {"workspace_id": workspace_id, "activity_type": activity_type, "description": description[:300]}
        )
