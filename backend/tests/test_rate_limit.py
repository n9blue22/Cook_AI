"""RateLimiter: cửa sổ trượt (đồng hồ giả), không trừ khi bị chặn, lớp theo email, quota ngày + trần override."""

import asyncio
from datetime import date, datetime

import pytest

from app.services.rate_limit import (
    HOUR,
    MINUTE,
    POLICIES,
    VN_TZ,
    DailyQuota,
    RateLimitedError,
    RateLimiter,
    daily_cap,
    seconds_until_vn_midnight,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeAdmin:
    """Giả RPC consume_daily_quota: đếm trong dict, all-or-nothing như hàm Postgres."""

    def __init__(self) -> None:
        self.used: dict[str, int] = {}

    def rpc(self, name: str, params: dict):
        allowed = all(self.used.get(b, 0) < limit for b, limit in zip(params["p_buckets"], params["p_limits"]))
        if allowed:
            for bucket in params["p_buckets"]:
                self.used[bucket] = self.used.get(bucket, 0) + 1
        return _Executable(allowed)

    def table(self, name: str) -> "_UsageQuery":
        return _UsageQuery(self.used)


class _UsageQuery:
    """Giả select bucket,used từ api_quota_usage (mọi dòng trong FakeAdmin coi là của hôm nay)."""

    def __init__(self, used: dict[str, int]) -> None:
        self.used, self.buckets = used, []

    def select(self, columns: str) -> "_UsageQuery":
        return self

    def eq(self, column: str, value: str) -> "_UsageQuery":
        return self

    def in_(self, column: str, values: list[str]) -> "_UsageQuery":
        self.buckets = values
        return self

    async def execute(self) -> "_Executable":
        return _Executable([{"bucket": b, "used": self.used[b]} for b in self.buckets if b in self.used])


class _Executable:
    def __init__(self, data) -> None:
        self.data = data

    async def execute(self) -> "_Executable":
        return self


def test_short_window_does_not_erase_long_window_history() -> None:
    clock = FakeClock()
    limiter = RateLimiter(admin=None, clock=clock)
    for _ in range(4):  # "login": 5/phút, 20/giờ
        for _ in range(5):
            limiter.check("login", "ip:1")
        clock.now += MINUTE + 1
    # 20 lượt trong 1 giờ: cửa sổ phút đã trống nhưng cửa sổ giờ phải chặn
    with pytest.raises(RateLimitedError) as blocked:
        limiter.check("login", "ip:1")
    assert blocked.value.retry_after > MINUTE  # phải chờ lượt cũ nhất trong giờ hết hạn, không phải 1 phút


def test_blocked_request_is_not_counted_and_window_slides() -> None:
    clock = FakeClock()
    limiter = RateLimiter(admin=None, clock=clock)
    for _ in range(3):  # "suggest": 3/phút
        limiter.check("suggest", "user:a")
    for _ in range(5):
        with pytest.raises(RateLimitedError):
            limiter.check("suggest", "user:a")
    limiter.check("suggest", "user:b")  # user khác không bị ảnh hưởng
    clock.now += MINUTE + 1
    limiter.check("suggest", "user:a")  # lượt bị chặn không cộng dồn → hết phút là dùng lại được


def test_per_email_layer_blocks_across_ips() -> None:
    clock = FakeClock()
    limiter = RateLimiter(admin=None, clock=clock)
    limiter.check("forgot_password", "ip:1", email="A@Example.com")
    with pytest.raises(RateLimitedError):  # 1/phút theo email, đổi IP vẫn bị chặn, không phân biệt hoa thường
        limiter.check("forgot_password", "ip:2", email="a@example.com")


def test_daily_quota_is_all_or_nothing_between_user_and_global_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUGGEST_DAILY_CAP", "2")
    admin = FakeAdmin()
    limiter = RateLimiter(admin=admin)

    asyncio.run(limiter.consume_daily("suggest", "a"))
    asyncio.run(limiter.consume_daily("suggest", "b"))
    with pytest.raises(RateLimitedError) as blocked:  # trần tổng 2 đã hết dù user c chưa dùng lượt nào
        asyncio.run(limiter.consume_daily("suggest", "c"))

    assert admin.used == {"user:a:suggest": 1, "global:suggest": 2, "user:b:suggest": 1}
    assert 0 < blocked.value.retry_after <= 24 * HOUR


def test_ensure_daily_available_only_reads_and_record_after_success_never_raises(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("IMAGE_DAILY_CAP", "1")
    admin = FakeAdmin()
    limiter = RateLimiter(admin=admin)

    asyncio.run(limiter.ensure_daily_available("dish_image_generate", "a"))
    asyncio.run(limiter.ensure_daily_available("dish_image_generate", "b"))  # 2 request cùng qua bước kiểm tra
    assert admin.used == {}  # kiểm tra không trừ gì

    asyncio.run(limiter.record_daily_after_success("dish_image_generate", "a"))
    asyncio.run(limiter.record_daily_after_success("dish_image_generate", "b"))  # vượt trần do race: chỉ log
    assert admin.used == {"user:a:dish_image_generate": 1, "global:dish_image_generate": 1}
    assert "vượt trần" in caplog.text

    with pytest.raises(RateLimitedError):
        asyncio.run(limiter.ensure_daily_available("dish_image_generate", "c"))


def test_daily_cap_override_expires_after_until_date(monkeypatch: pytest.MonkeyPatch) -> None:
    quota = POLICIES["suggest"].daily
    monkeypatch.setenv("SUGGEST_DAILY_CAP", "15")
    monkeypatch.setenv("SUGGEST_DAILY_CAP_OVERRIDE", "60")
    monkeypatch.setenv("DAILY_CAP_OVERRIDE_UNTIL", "2026-10-05")

    assert daily_cap(quota, today=date(2026, 10, 5)) == 60  # ngày demo
    assert daily_cap(quota, today=date(2026, 10, 6)) == 15  # tự về trần thường, không cần nhớ sửa env
    monkeypatch.setenv("SUGGEST_DAILY_CAP_OVERRIDE", "nhieu")
    assert daily_cap(quota, today=date(2026, 10, 5)) == 15  # sai định dạng → không nâng trần


def test_default_suggest_cap_is_15() -> None:
    assert POLICIES["suggest"].daily == DailyQuota(20, "SUGGEST_DAILY_CAP", 15)


def test_seconds_until_vn_midnight() -> None:
    assert seconds_until_vn_midnight(datetime(2026, 9, 27, 23, 59, 0, tzinfo=VN_TZ)) == 61


def test_refresh_allows_20_per_minute_and_300_per_hour_per_ip() -> None:
    clock = FakeClock()
    limiter = RateLimiter(admin=None, clock=clock)
    for _ in range(20):
        limiter.check("refresh", "ip:1")
    with pytest.raises(RateLimitedError) as blocked:
        limiter.check("refresh", "ip:1")
    assert blocked.value.retry_after <= MINUTE + 1  # chỉ chờ cửa sổ phút, không phải cả giờ
    for _ in range(14):  # đủ 300 lượt/giờ: 15 phút × 20
        clock.now += MINUTE
        for _ in range(20):
            limiter.check("refresh", "ip:1")
    clock.now += MINUTE
    with pytest.raises(RateLimitedError):
        limiter.check("refresh", "ip:1")
