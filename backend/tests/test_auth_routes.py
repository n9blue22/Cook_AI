"""Route auth: luật mật khẩu + HIBP, cookie httpOnly cho web, không dò được email, dịch lỗi không lộ chi tiết,
rate limit đăng nhập. Supabase Auth + HIBP giả bằng httpx.MockTransport (chạy qua SupabaseAuthApi thật)."""

import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rate_limiter
from app.api.routes.auth import FORGOT_MESSAGE, REFRESH_COOKIE, REGISTER_MESSAGE, get_auth_api
from app.core.config import get_settings
from app.main import app
from app.services.auth_service import GENERIC_AUTH_FAILURE, SupabaseAuthApi
from app.services.rate_limit import RateLimiter

GOOD_PASSWORD = "Dung-mat-khau-1!"
PWNED_PASSWORD = "Password123!"  # đạt luật độ mạnh nhưng HIBP giả báo đã rò rỉ
EXISTING_EMAIL = "da-co@example.com"
BROKEN_EMAIL = "gay-loi@example.com"  # Supabase giả trả lỗi lạ kèm chi tiết nội bộ
REJECTED_EMAIL = "bi-chan@example.com"  # Supabase từ chối địa chỉ (vd domain không nhận thư)


class FakeSupabaseAuth:
    """Giả REST /auth/v1 + HIBP; ghi lại request để kiểm tra."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.pwnedpasswords.com":
            return self._hibp(request)
        body = json.loads(request.content) if request.content else {}
        path = request.url.path.removeprefix("/auth/v1")
        self.calls.append((path, {**body, **dict(request.url.params)}))
        if body.get("email") == REJECTED_EMAIL:
            return httpx.Response(400, json={"error_code": "email_address_invalid"})
        if path == "/signup" and body["email"] == EXISTING_EMAIL:
            return httpx.Response(422, json={"error_code": "user_already_exists"})
        if path == "/token":
            return self._token(request.url.params["grant_type"], body)
        return httpx.Response(200, json={})

    def _token(self, grant: str, body: dict) -> httpx.Response:
        if grant == "password" and body["email"] == BROKEN_EMAIL:
            return httpx.Response(500, json={"msg": 'pq: relation "auth.users" does not exist at /srv/gotrue/db.go:42'})
        ok = (grant == "password" and body["password"] == GOOD_PASSWORD) or body.get("refresh_token") == "rt-1"
        if not ok:
            code = "invalid_credentials" if grant == "password" else "refresh_token_not_found"
            return httpx.Response(400, json={"error_code": code})
        next_refresh = "rt-2" if grant == "refresh_token" else "rt-1"
        return httpx.Response(200, json={
            "access_token": "at", "refresh_token": next_refresh, "expires_in": 3600,
            "user": {"id": "u-1", "email": "a@example.com"},
        })

    @staticmethod
    def _hibp(request: httpx.Request) -> httpx.Response:
        digest = hashlib.sha1(PWNED_PASSWORD.encode()).hexdigest().upper()  # noqa: S324
        if request.url.path.endswith(digest[:5]):
            return httpx.Response(200, text=f"0000000000000000000000000000000000A:0\n{digest[5:]}:12345")
        return httpx.Response(200, text="0000000000000000000000000000000000A:1")


@pytest.fixture
def fake_auth():
    fake = FakeSupabaseAuth()
    api = SupabaseAuthApi("https://supabase.test", "pub", httpx.AsyncClient(transport=httpx.MockTransport(fake)))
    app.dependency_overrides[get_auth_api] = lambda: api
    limiter = RateLimiter(admin=None)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield fake
    app.dependency_overrides.clear()


def post(path: str, body: dict, **kwargs) -> httpx.Response:
    return TestClient(app).post(f"/api/v1/auth{path}", json=body, **kwargs)


def test_register_enforces_password_rules_before_calling_supabase(fake_auth: FakeSupabaseAuth) -> None:
    weak = post("/register", {"email": "moi@example.com", "password": "abc"})
    pwned = post("/register", {"email": "moi@example.com", "password": PWNED_PASSWORD})

    assert weak.status_code == 422 and "chữ hoa" in weak.json()["detail"] and "8 ký tự" in weak.json()["detail"]
    assert pwned.status_code == 422 and "rò rỉ" in pwned.json()["detail"]
    assert fake_auth.calls == []


def test_register_does_not_reveal_whether_email_exists(fake_auth: FakeSupabaseAuth) -> None:
    new = post("/register", {"email": "moi@example.com", "password": GOOD_PASSWORD})
    existing = post("/register", {"email": EXISTING_EMAIL, "password": GOOD_PASSWORD})

    assert new.status_code == existing.status_code == 200
    assert new.json() == existing.json() == {"message": REGISTER_MESSAGE}
    assert fake_auth.calls[0][1]["redirect_to"] == f"{get_settings().frontend_url}/login?verified=1"


def test_web_login_keeps_refresh_token_in_httponly_cookie(fake_auth: FakeSupabaseAuth) -> None:
    web = post("/login", {"email": "a@example.com", "password": GOOD_PASSWORD, "client": "web"})
    native = post("/login", {"email": "a@example.com", "password": GOOD_PASSWORD, "client": "native"})

    cookie = web.headers["set-cookie"]
    assert web.json()["refresh_token"] is None and "rt-1" in cookie
    assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=none", "Path=/api/v1/auth"))
    assert native.json()["refresh_token"] == "rt-1" and "set-cookie" not in native.headers


def test_refresh_reads_cookie_and_rejects_missing_token(fake_auth: FakeSupabaseAuth) -> None:
    refreshed = post("/refresh", {"client": "web"}, cookies={REFRESH_COOKIE: "rt-1"})
    missing = post("/refresh", {"client": "web"})

    assert refreshed.status_code == 200 and "rt-2" in refreshed.headers["set-cookie"]
    assert missing.status_code == 401


def test_login_errors_are_translated_without_leaking_internals(fake_auth: FakeSupabaseAuth) -> None:
    wrong = post("/login", {"email": "a@example.com", "password": "Sai-mat-khau-1!"})
    broken = post("/login", {"email": BROKEN_EMAIL, "password": GOOD_PASSWORD})

    assert wrong.status_code == 401 and wrong.json()["detail"] == "Email hoặc mật khẩu không đúng"
    assert broken.status_code == 502 and broken.json() == {"detail": GENERIC_AUTH_FAILURE}
    assert not any(leak in broken.text for leak in ("relation", "auth.users", "/srv/", ".go"))


def test_validation_error_never_echoes_password(fake_auth: FakeSupabaseAuth) -> None:
    response = post("/login", {"email": "khong-phai-email", "password": "Bi-mat-cua-toi-9!"})

    assert response.status_code == 422
    assert "Bi-mat-cua-toi-9!" not in response.text and "input" not in response.text


def test_forgot_password_answers_the_same_for_any_email(fake_auth: FakeSupabaseAuth) -> None:
    assert post("/forgot-password", {"email": "co-that@example.com"}).json() == {"message": FORGOT_MESSAGE}
    assert post("/forgot-password", {"email": "khong-ton-tai@example.com"}).json() == {"message": FORGOT_MESSAGE}


def test_login_is_rate_limited_per_ip(fake_auth: FakeSupabaseAuth) -> None:
    body = {"email": "a@example.com", "password": "Sai-mat-khau-1!"}
    statuses = [post("/login", body).status_code for _ in range(6)]

    assert statuses == [401] * 5 + [429]
    blocked = post("/login", body)
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0


def test_email_rejected_by_supabase_is_a_user_error_not_outage(fake_auth: FakeSupabaseAuth) -> None:
    forgot = post("/forgot-password", {"email": REJECTED_EMAIL})
    register = post("/register", {"email": REJECTED_EMAIL, "password": GOOD_PASSWORD})

    assert forgot.status_code == register.status_code == 422
    assert forgot.json()["detail"] != GENERIC_AUTH_FAILURE


def test_refresh_429_sends_retry_after_readable_by_browser(fake_auth: FakeSupabaseAuth) -> None:
    origin = "http://localhost:8081"  # DEV_FRONTEND_URL, luôn nằm trong CORS_ORIGINS
    responses = [post("/refresh", {"client": "native", "refresh_token": "rt-1"}, headers={"Origin": origin})
                 for _ in range(21)]
    limited = responses[-1]
    assert [r.status_code for r in responses[:20]] == [200] * 20
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    assert "retry-after" in limited.headers["access-control-expose-headers"].lower()
