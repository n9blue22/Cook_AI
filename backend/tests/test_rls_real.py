"""RLS kiểm chứng bằng request THẬT: 2 tài khoản, JWT thật của từng người, gọi thẳng PostgREST của Supabase.

User A không được đọc / sửa / xoá / ghi hộ dữ liệu của user B ở pantry_items, saved_recipes, meal_logs,
user_profiles, user_allergens. Có đối chứng: A vẫn thấy dữ liệu của chính mình (tránh test "pass" vì bảng rỗng).
Tạo user bằng admin API (đã xác minh email sẵn, không gửi thư) và xoá sạch sau khi chạy.
"""

import uuid
from dataclasses import dataclass

import httpx
import pytest

from app.core.config import get_settings
from scripts.supabase_admin import create_admin_client

SETTINGS = get_settings()
REST = f"{SETTINGS.supabase_url}/rest/v1"
RECIPE_ID = 2648  # công thức có thật trong DB (FK của saved_recipes / meal_logs)
INGREDIENT_ID = 93  # Ức gà
FORBIDDEN = 403  # PostgREST: ghi vi phạm RLS (42501)


@dataclass(frozen=True)
class RlsUser:
    id: str
    token: str

    def headers(self, prefer: str = "return=representation") -> dict[str, str]:
        return {"apikey": SETTINGS.supabase_publishable_key, "Authorization": f"Bearer {self.token}", "Prefer": prefer}


def _sign_in(email: str, password: str) -> str:
    response = httpx.post(
        f"{SETTINGS.supabase_url}/auth/v1/token", params={"grant_type": "password"},
        headers={"apikey": SETTINGS.supabase_publishable_key}, json={"email": email, "password": password}, timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def users() -> tuple[RlsUser, RlsUser]:
    admin = create_admin_client()
    created: list[str] = []
    try:
        pair = []
        for label in ("a", "b"):
            email, password = f"rls-{label}-{uuid.uuid4().hex[:10]}@example.com", f"Rls-{uuid.uuid4().hex}-9!"
            user = admin.auth.admin.create_user({"email": email, "password": password, "email_confirm": True}).user
            created.append(user.id)
            pair.append(RlsUser(user.id, _sign_in(email, password)))
        yield tuple(pair)
    finally:
        for user_id in created:
            admin.auth.admin.delete_user(user_id)  # on delete cascade dọn luôn dữ liệu test


def _rows_for_a(a: RlsUser) -> dict[str, dict]:
    return {
        "pantry_items": {"user_id": a.id, "ingredient_id": INGREDIENT_ID, "quantity": 2},
        "saved_recipes": {"user_id": a.id, "recipe_id": RECIPE_ID},
        "meal_logs": {"user_id": a.id, "recipe_id": RECIPE_ID, "kcal": 320, "protein_g": 18, "carb_g": 9, "fat_g": 23},
    }


def test_user_cannot_read_update_delete_or_write_as_another_user(users: tuple[RlsUser, RlsUser]) -> None:
    a, b = users
    with httpx.Client(timeout=20) as http:
        for table, row in _rows_for_a(a).items():
            created = http.post(f"{REST}/{table}", headers=a.headers(), json=row)
            assert created.status_code == 201, (table, created.text)
            row_filter = {"id": f"eq.{created.json()[0]['id']}"}

            assert len(http.get(f"{REST}/{table}", headers=a.headers(), params=row_filter).json()) == 1, table  # đối chứng
            assert http.get(f"{REST}/{table}", headers=b.headers(), params=row_filter).json() == [], table
            assert http.patch(f"{REST}/{table}", headers=b.headers(), params=row_filter, json={"user_id": b.id}).json() == [], table
            assert http.delete(f"{REST}/{table}", headers=b.headers(), params=row_filter).json() == [], table
            assert http.post(f"{REST}/{table}", headers=b.headers(), json=row).status_code == FORBIDDEN, table
            assert len(http.get(f"{REST}/{table}", headers=a.headers(), params=row_filter).json()) == 1, table  # còn nguyên


def test_profiles_and_allergens_are_private(users: tuple[RlsUser, RlsUser]) -> None:
    a, b = users
    with httpx.Client(timeout=20) as http:
        own = {"user_id": f"eq.{a.id}"}
        assert len(http.get(f"{REST}/user_profiles", headers=a.headers(), params=own).json()) == 1  # trigger đã tạo
        http.post(f"{REST}/rpc/set_my_allergens", headers=a.headers(), json={"p_slugs": ["egg", "fish"]}).raise_for_status()
        assert len(http.get(f"{REST}/user_allergens", headers=a.headers(), params=own).json()) == 2

        assert http.get(f"{REST}/user_profiles", headers=b.headers(), params=own).json() == []
        assert http.patch(f"{REST}/user_profiles", headers=b.headers(), params=own, json={"diet_type": "vegan"}).json() == []
        assert http.get(f"{REST}/user_allergens", headers=b.headers(), params=own).json() == []
        assert http.delete(f"{REST}/user_allergens", headers=b.headers(), params=own).json() == []
        forged = http.post(f"{REST}/user_allergens", headers=b.headers(), json={"user_id": a.id, "allergen_id": 1})
        assert forged.status_code == FORBIDDEN
        assert http.get(f"{REST}/user_profiles", headers=a.headers(), params=own).json()[0]["diet_type"] == "omnivore"


def test_anonymous_key_sees_no_user_data(users: tuple[RlsUser, RlsUser]) -> None:
    anon = {"apikey": SETTINGS.supabase_publishable_key, "Authorization": f"Bearer {SETTINGS.supabase_publishable_key}"}
    for table in ("pantry_items", "saved_recipes", "meal_logs", "user_profiles", "user_allergens", "api_quota_usage"):
        response = httpx.get(f"{REST}/{table}", headers=anon, timeout=20)
        assert response.status_code in (401, 403) or response.json() == [], (table, response.status_code)


def test_search_recipes_rpc_closed_to_clients(users: tuple[RlsUser, RlsUser]) -> None:
    """Chỉ backend (secret key, có rate limit) gọi được — client có JWT hay không đều bị chặn."""
    body = {"query_embedding": [0.0] * 1024, "p_diet": "omnivore", "p_allergens": [], "p_ingredient_ids": [INGREDIENT_ID]}
    for headers in (users[0].headers(), {"apikey": SETTINGS.supabase_publishable_key}):
        assert httpx.post(f"{REST}/rpc/search_recipes", headers=headers, json=body, timeout=20).status_code in (401, 403)
