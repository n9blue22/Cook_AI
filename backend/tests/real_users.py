"""Helper cho các test chạy với Supabase thật: tạo user tạm đã đăng nhập, pool HTTP cho TestClient."""

import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

import httpx

from app.api.deps import get_jwt_verifier, get_rate_limiter
from app.core.config import get_settings
from app.main import app
from app.services.auth_tokens import JwtVerifier
from app.services.rate_limit import RateLimiter
from scripts.supabase_admin import create_admin_client

SETTINGS = get_settings()


def sign_in(email: str, password: str) -> str:
    """Đăng nhập bằng mật khẩu qua Supabase Auth → access token thật (ES256)."""
    response = httpx.post(
        f"{SETTINGS.supabase_url}/auth/v1/token", params={"grant_type": "password"},
        headers={"apikey": SETTINGS.supabase_publishable_key}, json={"email": email, "password": password}, timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@contextmanager
def signed_in_users(prefix: str, count: int) -> Iterator[list[dict[str, str]]]:
    """`count` user tạm (admin API, đã xác minh email) → header Authorization của từng người; xoá khi xong
    (on delete cascade dọn dữ liệu)."""
    admin = create_admin_client()
    created: list[str] = []
    try:
        headers = []
        for _ in range(count):
            email, password = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com", f"Pw-{uuid.uuid4().hex}-9!"
            created.append(admin.auth.admin.create_user({"email": email, "password": password, "email_confirm": True}).user.id)
            headers.append({"Authorization": f"Bearer {sign_in(email, password)}"})
        yield headers
    finally:
        for user_id in created:
            admin.auth.admin.delete_user(user_id)


def saved_recipe_body(recipe_id: int, title: str) -> dict:
    """Body hợp lệ cho POST /saved (1 nguyên liệu ức gà, 1 bước nấu)."""
    return {
        "recipe_id": recipe_id, "source": "adapted", "title": title, "servings": 2,
        "ingredients": [{"ingredient_id": 93, "name": "Ức gà", "amount": 200, "unit": "g"}],
        "steps": [{"step_no": 1, "action": "Áp chảo đến khi chín", "temperature_c": 74, "duration_sec": 600}],
        "rest_sec": 0, "nutrition_per_serving": {"kcal": 165, "protein_g": 31, "carb_g": 0, "fat_g": 3.6},
        "score": 0.9, "has_unmapped_ingredients": False,
    }


async def fresh_user_http() -> AsyncIterator[httpx.AsyncClient]:
    """Thay deps.get_user_http khi dùng TestClient không chạy lifespan: TestClient mở event loop mới cho mỗi
    request nên pool dùng chung giữa các request sẽ gắn với loop đã đóng → mỗi request 1 client riêng."""
    async with httpx.AsyncClient() as http:
        yield http


@asynccontextmanager
async def app_on_shared_pool() -> AsyncIterator[tuple[httpx.AsyncClient, httpx.AsyncClient, list[httpx.Request]]]:
    """App chạy trong 1 event loop như server thật (ASGITransport), JWT + JWKS thật, pool HTTP dùng chung thật
    (vai trò main.lifespan). Trả (client gọi API, pool dùng chung, các request pool đã gửi tới Supabase)."""
    sent: list[httpx.Request] = []

    async def remember(request: httpx.Request) -> None:
        sent.append(request)

    verifier, limiter = JwtVerifier(SETTINGS.supabase_url), RateLimiter(admin=None)
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        async with httpx.AsyncClient(timeout=30, event_hooks={"request": [remember]}) as shared_http:
            app.state.http = shared_http
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
                yield client, shared_http, sent
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "http"):
            del app.state.http
