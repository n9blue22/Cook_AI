"""Đăng ký / đăng nhập / làm mới / đăng xuất / quên + đặt lại mật khẩu qua REST API của Supabase Auth.

Gọi REST thẳng (không qua supabase-py auth client): client đó giữ session của user vừa đăng nhập trong chính nó,
dùng chung cho mọi request sẽ lẫn session giữa các user. Ở đây mỗi lời gọi tự mang token, không giữ trạng thái.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.password_policy import is_password_pwned, password_problems

logger = logging.getLogger(__name__)

AUTH_TIMEOUT_SEC = 15.0
GENERIC_AUTH_FAILURE = "Dịch vụ đăng nhập đang lỗi, thử lại sau"
# error_code của Supabase Auth → (HTTP status trả client, câu tiếng Việt). Mã lạ → GENERIC_AUTH_FAILURE.
_KNOWN_ERRORS: dict[str, tuple[int, str]] = {
    "invalid_credentials": (401, "Email hoặc mật khẩu không đúng"),
    "email_not_confirmed": (403, "Email chưa được xác minh — kiểm tra hộp thư"),
    "email_address_invalid": (422, "Địa chỉ email này không nhận được thư — dùng email khác"),
    "weak_password": (422, "Mật khẩu chưa đủ mạnh"),
    "same_password": (422, "Mật khẩu mới phải khác mật khẩu cũ"),
    "over_request_rate_limit": (429, "Thao tác quá nhiều lần, thử lại sau"),
    "over_email_send_rate_limit": (429, "Đã gửi quá nhiều email, thử lại sau"),
    "refresh_token_not_found": (401, "Phiên đăng nhập đã hết hạn, đăng nhập lại"),
    "refresh_token_already_used": (401, "Phiên đăng nhập đã hết hạn, đăng nhập lại"),
    "session_not_found": (401, "Phiên đăng nhập đã hết hạn, đăng nhập lại"),
    "bad_jwt": (401, "Phiên đăng nhập đã hết hạn, đăng nhập lại"),
}
# Đăng ký email đã tồn tại → trả như thành công, không cho dò email nào đã có tài khoản.
_SILENT_SUCCESS = frozenset({"user_already_exists", "email_exists"})


class AuthError(Exception):
    """Lỗi auth đã dịch sang câu cho user; status_code là mã HTTP trả client."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AuthSession:
    """Token trả về sau khi đăng nhập / làm mới."""

    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    email: str


class SupabaseAuthApi:
    """Bọc REST /auth/v1 của Supabase; không giữ session."""

    def __init__(self, supabase_url: str, publishable_key: str, http: httpx.AsyncClient) -> None:
        self._base = f"{supabase_url}/auth/v1"
        self._key = publishable_key
        self.http = http

    async def sign_up(self, email: str, password: str, redirect_to: str) -> None:
        """Tạo tài khoản; Supabase gửi email xác minh (bắt buộc xác minh trước khi đăng nhập)."""
        await self._call("POST", "/signup", {"email": email, "password": password}, params={"redirect_to": redirect_to})

    async def sign_in(self, email: str, password: str) -> AuthSession:
        """Đăng nhập email + mật khẩu."""
        body = await self._call("POST", "/token", {"email": email, "password": password}, params={"grant_type": "password"})
        return _session_from(body)

    async def refresh(self, refresh_token: str) -> AuthSession:
        """Đổi refresh token lấy cặp token mới (refresh token cũ hết hiệu lực)."""
        body = await self._call("POST", "/token", {"refresh_token": refresh_token}, params={"grant_type": "refresh_token"})
        return _session_from(body)

    async def sign_out(self, access_token: str) -> None:
        """Huỷ session hiện tại phía Supabase (refresh token không dùng lại được)."""
        await self._call("POST", "/logout", None, params={"scope": "local"}, token=access_token)

    async def send_password_reset(self, email: str, redirect_to: str) -> None:
        """Gửi email đặt lại mật khẩu; link dẫn về redirect_to kèm token khôi phục."""
        await self._call("POST", "/recover", {"email": email}, params={"redirect_to": redirect_to})

    async def update_password(self, access_token: str, new_password: str) -> None:
        """Đổi mật khẩu bằng access token (token khôi phục từ link email)."""
        await self._call("PUT", "/user", {"password": new_password}, token=access_token)

    async def _call(
        self, method: str, path: str, json: dict | None, params: dict | None = None, token: str | None = None,
    ) -> dict[str, Any]:
        headers = {"apikey": self._key, "Authorization": f"Bearer {token or self._key}"}
        try:
            response = await self.http.request(
                method, self._base + path, json=json, params=params, headers=headers, timeout=AUTH_TIMEOUT_SEC,
            )
        except httpx.HTTPError as error:
            logger.warning("Supabase Auth không phản hồi (%s %s): %s", method, path, error)
            raise AuthError(503, GENERIC_AUTH_FAILURE) from error
        if response.is_success:
            return response.json() if response.content else {}
        return _raise_auth_error(method, path, response)


def _raise_auth_error(method: str, path: str, response: httpx.Response) -> dict[str, Any]:
    """Dịch lỗi Supabase Auth; mã lạ chỉ ghi log chi tiết, trả client câu chung chung."""
    code = _error_code(response)
    if code in _SILENT_SUCCESS:
        return {}
    if code in _KNOWN_ERRORS:
        raise AuthError(*_KNOWN_ERRORS[code])
    logger.error("Supabase Auth %s %s → %d %s", method, path, response.status_code, response.text[:300])
    raise AuthError(502, GENERIC_AUTH_FAILURE)


def _error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    return str(body.get("error_code") or body.get("error") or "")


def _session_from(body: dict[str, Any]) -> AuthSession:
    user = body.get("user") or {}
    return AuthSession(
        access_token=body["access_token"], refresh_token=body["refresh_token"], expires_in=int(body["expires_in"]),
        user_id=user.get("id", ""), email=user.get("email", ""),
    )


async def check_new_password(password: str, http: httpx.AsyncClient) -> None:
    """Luật độ mạnh + chưa từng rò rỉ; không đạt → AuthError 422 với lý do cụ thể."""
    problems = password_problems(password)
    if problems:
        raise AuthError(422, "Mật khẩu cần " + ", ".join(problems))
    if await is_password_pwned(password, http):
        raise AuthError(422, "Mật khẩu này từng bị lộ trong các vụ rò rỉ dữ liệu — hãy chọn mật khẩu khác")
