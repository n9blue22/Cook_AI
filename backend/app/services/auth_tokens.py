"""Xác thực access token (JWT) của Supabase Auth bằng khoá công khai (JWKS) + client DB mang JWT của user.

Project ký JWT bằng ES256 (khoá bất đối xứng) → backend chỉ cần khoá công khai, không cần JWT secret.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import jwt
from postgrest import AsyncPostgrestClient

JWKS_PATH = "/auth/v1/.well-known/jwks.json"
ALLOWED_ALGORITHMS = ["ES256", "RS256"]  # bất đối xứng; KHÔNG nhận HS256/none
EXPECTED_AUDIENCE = "authenticated"
AUTHENTICATED_ROLE = "authenticated"
JWKS_CACHE_SEC = 3600
USER_DB_TIMEOUT_SEC = 15.0


class UnauthenticatedError(Exception):
    """Thiếu / sai / hết hạn access token."""


@dataclass(frozen=True)
class CurrentUser:
    """User đã xác thực của request hiện tại."""

    id: str
    access_token: str


class JwtVerifier:
    """Kiểm chữ ký + exp + aud + iss của access token; khoá công khai cache theo JWKS_CACHE_SEC."""

    def __init__(self, supabase_url: str) -> None:
        self._issuer = f"{supabase_url}/auth/v1"
        self._jwks = jwt.PyJWKClient(supabase_url + JWKS_PATH, cache_keys=True, lifespan=JWKS_CACHE_SEC)

    async def verify(self, token: str) -> CurrentUser:
        """Token hợp lệ → CurrentUser; mọi lỗi → UnauthenticatedError (không lộ lý do cụ thể ra client)."""
        try:
            signing_key = await asyncio.to_thread(self._jwks.get_signing_key_from_jwt, token)  # tải JWKS là I/O đồng bộ
            claims = jwt.decode(
                token, signing_key.key, algorithms=ALLOWED_ALGORITHMS, audience=EXPECTED_AUDIENCE,
                issuer=self._issuer, options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as error:
            raise UnauthenticatedError(str(error)) from error
        if claims.get("role") != AUTHENTICATED_ROLE or claims.get("is_anonymous"):
            raise UnauthenticatedError("Token không phải của user đã đăng nhập")
        return CurrentUser(id=claims["sub"], access_token=token)


@asynccontextmanager
async def user_db(supabase_url: str, publishable_key: str, user: CurrentUser) -> AsyncIterator[AsyncPostgrestClient]:
    """Client PostgREST mang JWT của user → RLS owner-only áp dụng. Mỗi request 1 client riêng, không dùng chung
    (header Authorization gắn vào client, dùng chung sẽ lẫn user)."""
    headers = {"apikey": publishable_key, "Authorization": f"Bearer {user.access_token}"}
    async with AsyncPostgrestClient(f"{supabase_url}/rest/v1", headers=headers, timeout=USER_DB_TIMEOUT_SEC) as client:
        yield client
