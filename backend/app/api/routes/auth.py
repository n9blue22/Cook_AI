"""Endpoint auth (feature-spec mục 6): đăng ký, đăng nhập, làm mới, đăng xuất, quên + đặt lại mật khẩu.

Web: refresh token nằm trong cookie httpOnly (JavaScript không đọc được), access token chỉ giữ trong bộ nhớ.
Mobile (client="native"): refresh token trả trong body để app lưu vào SecureStore.
"""

from typing import Literal

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import client_ip, get_rate_limiter, limit_ip, limit_user
from app.core.config import Settings, get_settings
from app.services.auth_service import AuthError, AuthSession, SupabaseAuthApi, check_new_password
from app.services.auth_tokens import CurrentUser
from app.services.rate_limit import RateLimiter

REFRESH_COOKIE = "bepai_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # trình duyệt chỉ gửi cookie cho /auth/*, không gửi cho mọi API
SESSION_MAX_AGE_SEC = 30 * 24 * 3600  # web: cookie hết hạn sau 30 ngày → phải đăng nhập lại
MAX_PASSWORD_INPUT = 128
REGISTER_MESSAGE = "Nếu email hợp lệ, bạn sẽ nhận được thư xác minh — mở thư để kích hoạt tài khoản"
FORGOT_MESSAGE = "Nếu email đã đăng ký, bạn sẽ nhận được link đặt lại mật khẩu"
EXPIRED_SESSION_MESSAGE = "Phiên đăng nhập đã hết hạn, đăng nhập lại"

ClientKind = Literal["web", "native"]

router = APIRouter(prefix="/auth", tags=["auth"])
logout_user = limit_user("default_user")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_INPUT)


class LoginBody(Credentials):
    client: ClientKind = "native"


class RefreshBody(BaseModel):
    refresh_token: str | None = None  # native gửi trong body; web để trống, backend đọc cookie
    client: ClientKind = "native"


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    access_token: str = Field(min_length=1)  # token khôi phục lấy từ link trong email
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD_INPUT)


class SessionOut(BaseModel):
    access_token: str
    expires_in: int
    user_id: str
    email: str
    refresh_token: str | None = None  # chỉ có với client="native"


class MessageOut(BaseModel):
    message: str


def get_auth_api(request: Request) -> SupabaseAuthApi:
    """SupabaseAuthApi dựng lúc khởi động (dùng chung 1 httpx client, không giữ session)."""
    return request.app.state.auth_api


@router.post("/register", response_model=MessageOut, dependencies=[Depends(limit_ip("register"))])
async def register(
    body: Credentials, api: SupabaseAuthApi = Depends(get_auth_api), settings: Settings = Depends(get_settings),
) -> MessageOut:
    """Tạo tài khoản; bắt buộc xác minh email trước khi đăng nhập. Không tiết lộ email đã tồn tại hay chưa."""
    await check_new_password(body.password, api.http)
    await api.sign_up(body.email, body.password, redirect_to=f"{settings.frontend_url}/login?verified=1")
    return MessageOut(message=REGISTER_MESSAGE)


@router.post("/login", response_model=SessionOut)
async def login(
    body: LoginBody, response: Response, ip: str = Depends(client_ip),
    limiter: RateLimiter = Depends(get_rate_limiter), api: SupabaseAuthApi = Depends(get_auth_api),
) -> SessionOut:
    """Email + mật khẩu → access token (+ refresh token theo loại client)."""
    limiter.check("login", f"ip:{ip}", email=body.email)
    return _session_out(await api.sign_in(body.email, body.password), body.client, response)


@router.post("/refresh", response_model=SessionOut, dependencies=[Depends(limit_ip("refresh"))])
async def refresh(
    body: RefreshBody, response: Response, api: SupabaseAuthApi = Depends(get_auth_api),
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> SessionOut:
    """Đổi refresh token (body hoặc cookie) lấy cặp token mới — client gọi trước khi access token hết hạn."""
    token = body.refresh_token or refresh_cookie
    if not token:
        raise AuthError(401, EXPIRED_SESSION_MESSAGE)
    return _session_out(await api.refresh(token), body.client, response)


@router.post("/logout", status_code=204)
async def logout(
    response: Response, user: CurrentUser = Depends(logout_user), api: SupabaseAuthApi = Depends(get_auth_api),
) -> Response:
    """Huỷ session phía Supabase + xoá cookie refresh (web)."""
    await api.sign_out(user.access_token)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, secure=True, httponly=True, samesite="none")
    response.status_code = 204
    return response


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(
    body: ForgotBody, ip: str = Depends(client_ip), limiter: RateLimiter = Depends(get_rate_limiter),
    api: SupabaseAuthApi = Depends(get_auth_api), settings: Settings = Depends(get_settings),
) -> MessageOut:
    """Gửi link đặt lại mật khẩu; luôn trả cùng một câu dù email có tồn tại hay không."""
    limiter.check("forgot_password", f"ip:{ip}", email=body.email)
    await api.send_password_reset(body.email, redirect_to=f"{settings.frontend_url}/reset-password")
    return MessageOut(message=FORGOT_MESSAGE)


@router.post("/reset-password", response_model=MessageOut, dependencies=[Depends(limit_ip("reset_password"))])
async def reset_password(body: ResetBody, api: SupabaseAuthApi = Depends(get_auth_api)) -> MessageOut:
    """Đặt mật khẩu mới bằng token khôi phục (cùng luật độ mạnh + kiểm tra rò rỉ như đăng ký)."""
    await check_new_password(body.new_password, api.http)
    await api.update_password(body.access_token, body.new_password)
    return MessageOut(message="Đã đổi mật khẩu — đăng nhập lại bằng mật khẩu mới")


def _session_out(session: AuthSession, client: ClientKind, response: Response) -> SessionOut:
    """Web: refresh token vào cookie httpOnly, không trả trong body. Native: trả trong body."""
    out = SessionOut(
        access_token=session.access_token, expires_in=session.expires_in, user_id=session.user_id, email=session.email,
    )
    if client == "native":
        return out.model_copy(update={"refresh_token": session.refresh_token})
    response.set_cookie(
        REFRESH_COOKIE, session.refresh_token, max_age=SESSION_MAX_AGE_SEC, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=True, samesite="none",  # frontend (Vercel) và API (Render) khác domain
    )
    return out
