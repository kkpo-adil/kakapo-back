from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from app.models.scientist_profile import ScientistProfile

PERIOD_DAYS = 30


@dataclass(frozen=True)
class QuotaStatus:
    allowed: bool
    quota: int
    used: int
    remaining: int
    period_start: datetime
    period_end: datetime


class QuotaExceededError(Exception):
    def __init__(self, status: QuotaStatus) -> None:
        super().__init__("Monthly KPT quota exceeded")
        self.status = status


class KPTQuotaService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _period_expired(period_start: datetime, now: datetime) -> bool:
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)
        return now - period_start >= timedelta(days=PERIOD_DAYS)

    def _reset_period_if_needed(self, scientist: ScientistProfile, now: datetime) -> None:
        if self._period_expired(scientist.kpt_quota_period_start, now):
            scientist.kpt_count_current_period = 0
            scientist.kpt_quota_period_start = now

    def get_status(self, scientist: ScientistProfile) -> QuotaStatus:
        now = self._now()
        self._reset_period_if_needed(scientist, now)
        period_end = scientist.kpt_quota_period_start + timedelta(days=PERIOD_DAYS)
        remaining = max(0, scientist.monthly_kpt_quota - scientist.kpt_count_current_period)
        return QuotaStatus(
            allowed=remaining > 0,
            quota=scientist.monthly_kpt_quota,
            used=scientist.kpt_count_current_period,
            remaining=remaining,
            period_start=scientist.kpt_quota_period_start,
            period_end=period_end,
        )

    def check_and_consume(self, scientist: ScientistProfile) -> QuotaStatus:
        status = self.get_status(scientist)
        if not status.allowed:
            raise QuotaExceededError(status)
        scientist.kpt_count_current_period += 1
        return self.get_status(scientist)
