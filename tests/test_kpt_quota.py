from datetime import datetime, timezone, timedelta
import pytest
from app.models.scientist_profile import ScientistProfile
from app.services.kpt_quota_service import KPTQuotaService, QuotaExceededError


def make_scientist(quota=5, used=0, days_ago=0):
    now = datetime.now(timezone.utc)
    s = ScientistProfile()
    s.monthly_kpt_quota = quota
    s.kpt_count_current_period = used
    s.kpt_quota_period_start = now - timedelta(days=days_ago)
    return s


def test_quota_allows_creation_when_under_limit():
    s = make_scientist(quota=5, used=2)
    status = KPTQuotaService().check_and_consume(s)
    assert status.used == 3
    assert status.remaining == 2


def test_quota_blocks_creation_when_at_limit():
    s = make_scientist(quota=5, used=5)
    with pytest.raises(QuotaExceededError) as exc_info:
        KPTQuotaService().check_and_consume(s)
    assert exc_info.value.status.remaining == 0


def test_quota_resets_after_period():
    s = make_scientist(quota=5, used=5, days_ago=31)
    status = KPTQuotaService().check_and_consume(s)
    assert s.kpt_count_current_period == 1
    assert status.remaining == 4


def test_quota_does_not_reset_within_period():
    s = make_scientist(quota=5, used=5, days_ago=15)
    with pytest.raises(QuotaExceededError):
        KPTQuotaService().check_and_consume(s)


def test_get_status_correct():
    s = make_scientist(quota=50, used=10)
    status = KPTQuotaService().get_status(s)
    assert status.quota == 50
    assert status.used == 10
    assert status.remaining == 40
    assert status.allowed is True
