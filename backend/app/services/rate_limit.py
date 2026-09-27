"""Rate limit: mục tiêu chính là giữ quota free tier (Gemini / Groq / Cloudflare), sau đó mới là chống lạm dụng.

- Cửa sổ ngắn (phút/giờ): đếm trong RAM, theo user_id (đã đăng nhập) hoặc IP / email.
- Hạn mức ngày cho endpoint tốn quota AI: đếm trong Postgres (consume_daily_quota) — Render free tắt server khi
  rảnh, đếm trong RAM sẽ về 0. Mỗi lượt trừ đồng thời quota của user và trần tổng toàn app.
"""

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from supabase import AsyncClient

logger = logging.getLogger(__name__)

MINUTE, HOUR = 60, 3600
VN_TZ = timezone(timedelta(hours=7))  # Việt Nam không có giờ mùa hè → múi cố định, không cần tzdata
OVERRIDE_UNTIL_ENV = "DAILY_CAP_OVERRIDE_UNTIL"
MAX_TRACKED_KEYS = 10_000  # vượt thì dọn key cũ


@dataclass(frozen=True)
class WindowRule:
    """Tối đa `limit` lượt trong `seconds` giây gần nhất."""

    limit: int
    seconds: int


@dataclass(frozen=True)
class DailyQuota:
    """Hạn mức ngày (giờ VN): theo từng user + trần tổng toàn app (đọc env, nâng tạm được bằng *_OVERRIDE)."""

    per_user: int
    cap_env: str
    default_cap: int


@dataclass(frozen=True)
class RatePolicy:
    """Luật cho 1 nhóm endpoint."""

    windows: tuple[WindowRule, ...]
    daily: DailyQuota | None = None
    per_email: tuple[WindowRule, ...] = field(default_factory=tuple)  # thêm 1 lớp theo email (đăng nhập, quên mật khẩu)


# Ngưỡng đã chốt (xem báo cáo trước khi code). /recipes/suggest chặt nhất: 1 lượt = tối đa 5 lời gọi LLM.
POLICIES: dict[str, RatePolicy] = {
    "recognize": RatePolicy((WindowRule(5, MINUTE),), DailyQuota(30, "RECOGNIZE_DAILY_CAP", 200)),
    "suggest": RatePolicy((WindowRule(3, MINUTE),), DailyQuota(20, "SUGGEST_DAILY_CAP", 15)),
    "dish_image": RatePolicy((WindowRule(10, MINUTE),)),  # gọi endpoint (kể cả lấy ảnh đã cache)
    "dish_image_generate": RatePolicy((), DailyQuota(10, "IMAGE_DAILY_CAP", 50)),  # chỉ lần sinh ảnh mới
    "login": RatePolicy((WindowRule(5, MINUTE), WindowRule(20, HOUR)), per_email=(WindowRule(10, 15 * MINUTE),)),
    "register": RatePolicy((WindowRule(3, HOUR),)),
    "forgot_password": RatePolicy((WindowRule(3, HOUR),), per_email=(WindowRule(1, MINUTE),)),
    "reset_password": RatePolicy((WindowRule(5, HOUR),)),
    "refresh": RatePolicy((WindowRule(30, HOUR),)),
    "profile": RatePolicy((WindowRule(60, MINUTE),)),
    "default_user": RatePolicy((WindowRule(60, MINUTE),)),
    "default_ip": RatePolicy((WindowRule(30, MINUTE),)),
}


class RateLimitedError(Exception):
    """Vượt ngưỡng; retry_after = số giây nên chờ (header Retry-After)."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """Cửa sổ trượt trong RAM + hạn mức ngày trong Postgres. 1 instance dùng chung cả app."""

    def __init__(self, admin: AsyncClient, clock=time.monotonic) -> None:
        self._admin = admin  # secret key: consume_daily_quota chỉ service_role gọi được
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def check(self, policy_name: str, identity: str, email: str | None = None) -> None:
        """Ghi 1 lượt cho identity (và email nếu có); vượt bất kỳ cửa sổ nào → RateLimitedError, không ghi gì."""
        policy = POLICIES[policy_name]
        # Mỗi cửa sổ một hàng đợi riêng: dùng chung thì cửa sổ ngắn dọn mất lịch sử của cửa sổ dài
        keyed = [(f"{policy_name}:{identity}:{rule.seconds}", rule) for rule in policy.windows]
        if email:
            keyed += [(f"{policy_name}:email:{email.lower()}:{rule.seconds}", rule) for rule in policy.per_email]
        now = self._clock()
        waits = [wait for key, rule in keyed if (wait := self._wait_needed(key, rule, now)) > 0]
        if waits:
            raise RateLimitedError("Bạn thao tác quá nhanh, thử lại sau ít phút", int(max(waits)) + 1)
        for key, _ in keyed:
            self._hits.setdefault(key, deque()).append(now)
        self._prune_if_large(now)

    async def consume_daily(self, policy_name: str, user_id: str) -> None:
        """Trừ 1 lượt quota ngày của user + trần tổng; hết một trong hai → RateLimitedError (không trừ gì)."""
        quota = POLICIES[policy_name].daily
        if quota is None:
            return
        buckets = [f"user:{user_id}:{policy_name}", f"global:{policy_name}"]
        limits = [quota.per_user, daily_cap(quota)]
        allowed = (await self._admin.rpc("consume_daily_quota", {"p_buckets": buckets, "p_limits": limits}).execute()).data
        if not allowed:
            raise RateLimitedError("Đã dùng hết lượt hôm nay, quay lại vào ngày mai", seconds_until_vn_midnight())

    def _wait_needed(self, key: str, rule: WindowRule, now: float) -> float:
        hits = self._hits.get(key)
        if not hits:
            return 0
        while hits and hits[0] <= now - rule.seconds:
            hits.popleft()
        if len(hits) < rule.limit:
            return 0
        return hits[-rule.limit] + rule.seconds - now  # chờ tới khi lượt cũ nhất trong `limit` lượt gần nhất hết hạn

    def _prune_if_large(self, now: float) -> None:
        # ponytail: dọn thô khi quá MAX_TRACKED_KEYS; nhiều instance thì chuyển sang Redis
        if len(self._hits) <= MAX_TRACKED_KEYS:
            return
        self._hits = {k: q for k, q in self._hits.items() if q and q[-1] > now - HOUR}


def daily_cap(quota: DailyQuota, today: date | None = None) -> int:
    """Trần tổng/ngày: <ENV>_OVERRIDE (nếu có và chưa qua DAILY_CAP_OVERRIDE_UNTIL) → <ENV> → mặc định."""
    today = today or datetime.now(VN_TZ).date()
    override, until = os.getenv(f"{quota.cap_env}_OVERRIDE"), os.getenv(OVERRIDE_UNTIL_ENV)
    try:
        if override and (not until or today <= date.fromisoformat(until)):
            return int(override)
        return int(os.getenv(quota.cap_env, quota.default_cap))
    except ValueError:
        logger.error("Giá trị trần quota sai định dạng (%s) — dùng mặc định %d", quota.cap_env, quota.default_cap)
        return quota.default_cap


def seconds_until_vn_midnight(now: datetime | None = None) -> int:
    """Số giây tới 0h (giờ VN) — lúc quota ngày được làm mới."""
    now = now or datetime.now(VN_TZ)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), VN_TZ)
    return int((tomorrow - now).total_seconds()) + 1
