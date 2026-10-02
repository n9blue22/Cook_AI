"""Helper cho các test chạy với Supabase thật: tạo user tạm đã đăng nhập, pool HTTP cho TestClient."""

import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

import httpx

from app.core.config import get_settings
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
