from datetime import date
from threading import Lock

from app.core.config import settings
from app.services.ai.exceptions import AIQuotaExceededError


class DailyUsageTracker:
    """Simple thread-safe daily request counter to protect AI usage quotas."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._day: date = date.today()
        self._count: int = 0

    def check_and_increment(self) -> int:
        with self._lock:
            today = date.today()
            if today != self._day:
                self._day = today
                self._count = 0
            if self._count >= settings.ai_daily_request_limit:
                raise AIQuotaExceededError(
                    f"Daily AI request limit ({settings.ai_daily_request_limit}) reached."
                )
            self._count += 1
            return self._count

    def get_status(self) -> dict[str, int]:
        with self._lock:
            today = date.today()
            if today != self._day:
                self._day = today
                self._count = 0
            return {
                "used_today": self._count,
                "daily_limit": settings.ai_daily_request_limit,
                "remaining_today": max(settings.ai_daily_request_limit - self._count, 0),
            }

    def reset(self) -> None:
        with self._lock:
            self._day = date.today()
            self._count = 0


usage_tracker = DailyUsageTracker()
