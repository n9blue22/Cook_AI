"""/pantry, /logs, /saved qua backend THẬT: 2 user thật, JWT thật, Supabase thật (RLS owner-only).

Mỗi user chỉ thấy / xoá được dữ liệu của mình; có đối chứng (A vẫn thấy dữ liệu của A) để test không "pass" vì rỗng.
Tạo user bằng admin API (đã xác minh email, không gửi thư) và xoá sau khi chạy — on delete cascade dọn dữ liệu.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from supabase import AsyncClient

from app.api.deps import get_admin_client, get_jwt_verifier, get_rate_limiter, get_user_http
from app.core.config import get_settings
from app.core.supabase_client import create_admin_client as create_async_admin_client
from app.main import app
from app.services.auth_tokens import JwtVerifier
from app.services.rate_limit import VN_TZ, RateLimiter
from tests.real_users import fresh_user_http, saved_recipe_body, signed_in_users

SETTINGS = get_settings()
RECIPE_ID = 2648  # công thức có thật trong DB
RECIPE_TITLE = "Khô Gà Lá Chanh"
FOODCOM_RECIPE_ID, FOODCOM_TITLE = 391, "cheesecake factory romano chicken"  # chưa kiểm duyệt: RLS ẩn với user
INGREDIENT_ID = 93  # Ức gà
MISSING_ID = 999_999_999


@pytest.fixture(scope="module")
def auth_headers() -> Iterator[tuple[dict[str, str], dict[str, str]]]:
    with signed_in_users("data", 2) as (a, b):
        yield a, b


async def _admin_client() -> AsyncClient:
    return await create_async_admin_client(SETTINGS)  # tạo trong event loop của TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    verifier, limiter = JwtVerifier(SETTINGS.supabase_url), RateLimiter(admin=None)
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_admin_client] = _admin_client
    app.dependency_overrides[get_user_http] = fresh_user_http
    yield TestClient(app)
    app.dependency_overrides.clear()


def _recipe(title: str) -> dict:
    return saved_recipe_body(RECIPE_ID, title)


def test_pantry_is_private_and_upserts(client: TestClient, auth_headers) -> None:
    a, b = auth_headers
    first = client.post("/api/v1/pantry", headers=a, json={"ingredient_id": INGREDIENT_ID, "quantity": 2, "unit": "miếng"})
    again = client.post("/api/v1/pantry", headers=a, json={"name": "ức gà", "expires_on": "2026-10-01"})  # tên gõ tay
    assert first.status_code == again.status_code == 201
    assert again.json() | {"expires_on": None} == first.json() | {"expires_on": None}  # cùng dòng, không nhân đôi
    assert again.json()["quantity"] == 2 and again.json()["name"] == "Ức gà"  # trường không gửi thì giữ nguyên
    item_id = first.json()["id"]

    assert [item["id"] for item in client.get("/api/v1/pantry", headers=a).json()] == [item_id]  # đối chứng
    assert client.get("/api/v1/pantry", headers=b).json() == []
    assert client.delete(f"/api/v1/pantry/{item_id}", headers=b).status_code == 404
    assert len(client.get("/api/v1/pantry", headers=a).json()) == 1  # B xoá hộ không được
    assert client.delete(f"/api/v1/pantry/{item_id}", headers=a).status_code == 204
    assert client.get("/api/v1/pantry", headers=a).json() == []


def test_pantry_rejects_bad_references(client: TestClient, auth_headers) -> None:
    a, _ = auth_headers
    unknown_name = client.post("/api/v1/pantry", headers=a, json={"name": "xyzzy không phải đồ ăn"})
    unknown_id = client.post("/api/v1/pantry", headers=a, json={"ingredient_id": MISSING_ID})
    both = client.post("/api/v1/pantry", headers=a, json={"ingredient_id": INGREDIENT_ID, "name": "ức gà"})
    assert unknown_name.status_code == unknown_id.status_code == both.status_code == 422
    assert "xyzzy" in unknown_name.json()["detail"]


def test_meal_logs_sum_per_vietnam_day_and_are_private(client: TestClient, auth_headers) -> None:
    a, b = auth_headers
    meal = {"recipe_id": RECIPE_ID, "kcal": 320.5, "protein_g": 18, "carb_g": 9, "fat_g": 23}
    assert client.post("/api/v1/logs", headers=a, json=meal).status_code == 204
    assert client.post("/api/v1/logs", headers=a, json=meal | {"recipe_id": None}).status_code == 204
    assert client.post("/api/v1/logs", headers=a, json=meal | {"recipe_id": FOODCOM_RECIPE_ID}).status_code == 204
    today = datetime.now(VN_TZ).date()

    summary = client.get("/api/v1/logs", headers=a, params={"date": today.isoformat()}).json()
    totals = {key: summary[key] for key in ("date", "kcal", "protein_g", "carb_g", "fat_g", "meals")}
    assert totals == {"date": today.isoformat(), "kcal": 961.5, "protein_g": 54.0, "carb_g": 27.0, "fat_g": 69.0, "meals": 3}
    # cũ trước; món Food.com (RLS ẩn với user) vẫn có tên vì đọc bằng admin
    assert [(e["recipe_id"], e["title"], e["kcal"]) for e in summary["entries"]] == [
        (RECIPE_ID, RECIPE_TITLE, 320.5), (None, None, 320.5), (FOODCOM_RECIPE_ID, FOODCOM_TITLE, 320.5)]
    assert client.get("/api/v1/logs", headers=a).json() == summary  # mặc định hôm nay giờ VN
    yesterday = client.get("/api/v1/logs", headers=a, params={"date": (today - timedelta(days=1)).isoformat()}).json()
    assert yesterday["meals"] == 0 and yesterday["entries"] == []
    assert client.get("/api/v1/logs", headers=b).json()["entries"] == []

    assert client.post("/api/v1/logs", headers=a, json=meal | {"kcal": -1}).status_code == 422
    assert client.post("/api/v1/logs", headers=a, json=meal | {"recipe_id": MISSING_ID}).status_code == 422


def test_user_can_delete_only_own_meal_log(client: TestClient, auth_headers) -> None:
    a, b = auth_headers
    meal = {"recipe_id": RECIPE_ID, "kcal": 111, "protein_g": 1, "carb_g": 1, "fat_g": 1}
    assert client.post("/api/v1/logs", headers=a, json=meal).status_code == 204
    assert client.post("/api/v1/logs", headers=b, json=meal).status_code == 204
    a_entry = next(e for e in client.get("/api/v1/logs", headers=a).json()["entries"] if e["kcal"] == 111)
    b_entry = next(e for e in client.get("/api/v1/logs", headers=b).json()["entries"] if e["kcal"] == 111)

    assert client.delete(f"/api/v1/logs/{a_entry['id']}", headers=b).status_code == 404  # RLS: B không xoá được của A
    assert a_entry in client.get("/api/v1/logs", headers=a).json()["entries"]  # đối chứng: của A vẫn còn
    assert client.delete(f"/api/v1/logs/{a_entry['id']}", headers=a).status_code == 204
    assert a_entry not in client.get("/api/v1/logs", headers=a).json()["entries"]
    assert client.delete(f"/api/v1/logs/{a_entry['id']}", headers=a).status_code == 404  # xoá lần 2
    assert client.delete(f"/api/v1/logs/{MISSING_ID}", headers=a).status_code == 404
    assert b_entry in client.get("/api/v1/logs", headers=b).json()["entries"]  # A xoá không đụng tới bữa của B


def test_saved_recipes_search_upsert_and_privacy(client: TestClient, auth_headers) -> None:
    a, b = auth_headers
    first = client.post("/api/v1/saved", headers=a, json={"recipe": _recipe("Ức gà áp chảo 100%")})
    again = client.post("/api/v1/saved", headers=a, json={"recipe": _recipe("Ức gà áp chảo sả")})
    assert first.status_code == again.status_code == 201
    assert again.json()["id"] == first.json()["id"]  # lưu lại = cập nhật, không nhân đôi
    assert datetime.fromisoformat(again.json()["saved_at"]) >= datetime.fromisoformat(first.json()["saved_at"])
    saved_id = again.json()["id"]

    listed = client.get("/api/v1/saved", headers=a).json()
    assert [s["recipe"]["title"] for s in listed] == ["Ức gà áp chảo sả"]
    # diet_type tra từ bảng recipes (cho bộ lọc "Chay"), có ở cả response POST lẫn GET
    assert listed[0]["diet_type"] == again.json()["diet_type"] in ("omnivore", "vegetarian", "vegan")
    assert len(client.get("/api/v1/saved", headers=a, params={"q": "ÁP CHẢO"}).json()) == 1
    assert client.get("/api/v1/saved", headers=a, params={"q": "%"}).json() == []  # % là ký tự thường, không phải wildcard
    assert client.get("/api/v1/saved", headers=b).json() == []
    assert client.delete(f"/api/v1/saved/{saved_id}", headers=b).status_code == 404
    assert client.delete(f"/api/v1/saved/{saved_id}", headers=a).status_code == 204
    assert client.get("/api/v1/saved", headers=a).json() == []

    missing = client.post("/api/v1/saved", headers=a, json={"recipe": _recipe("x") | {"recipe_id": MISSING_ID}})
    assert missing.status_code == 422


def test_user_data_endpoints_require_login(client: TestClient) -> None:
    for method, path in (("GET", "/pantry"), ("GET", "/logs"), ("GET", "/saved"), ("DELETE", "/saved/1"), ("DELETE", "/logs/1")):
        assert client.request(method, f"/api/v1{path}").status_code == 401
