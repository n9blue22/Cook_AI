"""Dependency dùng chung: user hiện tại (JWT), rate limit, client DB mang JWT của user."""

from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, Request
from postgrest import AsyncPostgrestClient

from app.core.config import Settings, get_settings
from app.services.auth_tokens import CurrentUser, JwtVerifier, UnauthenticatedError, user_db
from app.services.rate_limit import RateLimiter

BEARER_SCHEME = "bearer"


def get_rate_limiter(request: Request) -> RateLimiter:
    """RateLimiter dựng lúc khởi động (main.lifespan)."""
    return request.app.state.rate_limiter


def get_jwt_verifier(request: Request) -> JwtVerifier:
    """JwtVerifier dựng lúc khởi động (cache khoá JWKS)."""
    return request.app.state.jwt_verifier


def client_ip(request: Request) -> str:
    """IP client. Sau proxy (Render) phải chạy uvicorn --proxy-headers để lấy IP thật từ X-Forwarded-For."""
    return request.client.host if request.client else "unknown"


async def require_user(request: Request, verifier: JwtVerifier = Depends(get_jwt_verifier)) -> CurrentUser:
    """Header Authorization: Bearer <access token> hợp lệ → CurrentUser; thiếu/sai → 401."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != BEARER_SCHEME or not token.strip():
        raise UnauthenticatedError("Thiếu access token")
    return await verifier.verify(token.strip())


def limit_user(policy_name: str, consume_daily: bool = False) -> Callable[..., Awaitable[CurrentUser]]:
    """Bắt đăng nhập + rate limit theo user_id (+ trừ quota ngày nếu consume_daily).
    Gọi 1 lần ở cấp module rồi dùng lại object trả về — FastAPI chỉ cache dependency theo object."""

    async def dependency(
        user: CurrentUser = Depends(require_user), limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> CurrentUser:
        limiter.check(policy_name, f"user:{user.id}")
        if consume_daily:
            await limiter.consume_daily(policy_name, user.id)
        return user

    return dependency


def limit_ip(policy_name: str) -> Callable[..., Awaitable[str]]:
    """Rate limit theo IP cho endpoint không cần đăng nhập; trả IP."""

    async def dependency(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> str:
        ip = client_ip(request)
        limiter.check(policy_name, f"ip:{ip}")
        return ip

    return dependency


def user_db_dependency(
    user_dependency: Callable[..., Awaitable[CurrentUser]],
) -> Callable[..., AsyncIterator[AsyncPostgrestClient]]:
    """Client PostgREST mang JWT của user (RLS owner-only) cho 1 request, đóng khi xong."""

    async def dependency(
        user: CurrentUser = Depends(user_dependency), settings: Settings = Depends(get_settings),
    ) -> AsyncIterator[AsyncPostgrestClient]:
        async with user_db(settings.supabase_url, settings.supabase_publishable_key, user) as db:
            yield db

    return dependency
