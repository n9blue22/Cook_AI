"""Pool HTTP dùng chung (main.lifespan → deps.get_user_http) không làm lẫn dữ liệu giữa các user.

2 user thật + 1 bên gửi token sai bắn GET /pantry, /saved, /profile song song nhiều vòng qua CÙNG 1 httpx.AsyncClient,
trong cùng 1 event loop (ASGITransport) như server thật. Mỗi response chỉ được chứa dữ liệu của chính người gọi;
token sai luôn 401, không bao giờ thấy dữ liệu của ai.
"""

import asyncio

import httpx
import pytest

from app.api.deps import get_jwt_verifier, get_rate_limiter
from app.core.config import get_settings
from app.main import app
from app.services.auth_tokens import JwtVerifier
from app.services.rate_limit import RateLimiter
from tests.real_users import saved_recipe_body, signed_in_users

SETTINGS = get_settings()
A_INGREDIENT_ID, B_INGREDIENT_ID = 93, 16  # Ức gà / nguyên liệu khác, đều có thật trong danh mục
A_SAVED_RECIPE_ID = 2648
ROUNDS = 12  # 12 × 3 GET mỗi user < 60/phút (giới hạn default_user / profile)
ENDPOINTS = ("/pantry", "/saved", "/profile")
BASE = "http://test/api/v1"


async def _seed(client: httpx.AsyncClient, a: dict[str, str], b: dict[str, str]) -> None:
    """A: tủ có ức gà, đã lưu 1 món, ăn chay. B: tủ có nguyên liệu khác, chưa lưu gì, ăn mặn (mặc định)."""
    for headers, body in ((a, {"ingredient_id": A_INGREDIENT_ID}), (b, {"ingredient_id": B_INGREDIENT_ID})):
        assert (await client.post(f"{BASE}/pantry", headers=headers, json=body)).status_code == 201
    assert (await client.post(f"{BASE}/saved", headers=a, json={"recipe": saved_recipe_body(A_SAVED_RECIPE_ID, "Món riêng của A")})).status_code == 201
    assert (await client.patch(f"{BASE}/profile", headers=a, json={"diet_type": "vegetarian"})).status_code == 200


def _assert_own_data(owner: str, endpoint: str, body: object) -> None:
    expected = {
        ("a", "/pantry"): lambda data: [item["ingredient_id"] for item in data] == [A_INGREDIENT_ID],
        ("b", "/pantry"): lambda data: [item["ingredient_id"] for item in data] == [B_INGREDIENT_ID],
        ("a", "/saved"): lambda data: [s["recipe"]["title"] for s in data] == ["Món riêng của A"],
        ("b", "/saved"): lambda data: data == [],
        ("a", "/profile"): lambda data: data["diet_type"] == "vegetarian",
        ("b", "/profile"): lambda data: data["diet_type"] == "omnivore",
    }[(owner, endpoint)]
    assert expected(body), f"user {owner} {endpoint} thấy dữ liệu không phải của mình: {body}"


async def _hammer(client: httpx.AsyncClient, callers: dict[str, dict[str, str]]) -> None:
    calls = [(owner, endpoint) for _ in range(ROUNDS) for endpoint in ENDPOINTS for owner in callers]
    responses = await asyncio.gather(*(
        client.get(BASE + endpoint, headers=callers[owner]) for owner, endpoint in calls
    ))
    for (owner, endpoint), response in zip(calls, responses):
        if owner == "bad":
            assert response.status_code == 401 and "diet_type" not in response.text and "recipe" not in response.text
            continue
        assert response.status_code == 200, response.text
        _assert_own_data(owner, endpoint, response.json())


async def _run(a: dict[str, str], b: dict[str, str]) -> None:
    a_token = a["Authorization"].removeprefix("Bearer ")
    bad = {"Authorization": f"Bearer {a_token[:-6]}xxxxxx"}  # chữ ký sai: giống token của A nhưng bị sửa
    sent_tokens: list[str | None] = []

    async def remember_token(request: httpx.Request) -> None:
        sent_tokens.append(request.headers.get("authorization"))

    async with httpx.AsyncClient(timeout=30, event_hooks={"request": [remember_token]}) as shared_http:
        app.state.http = shared_http  # đúng vai trò pool dùng chung của main.lifespan
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport) as client:
            await _seed(client, a, b)
            await _hammer(client, {"a": a, "b": b, "bad": bad})
        assert "authorization" not in shared_http.headers  # pool dùng chung không bao giờ mang token
    # Cả A và B thật sự đi qua CÙNG pool, và mọi request ra ngoài đều mang token của đúng 1 người gọi
    assert set(sent_tokens) == {a["Authorization"], b["Authorization"]}


@pytest.fixture
def overrides():
    verifier, limiter = JwtVerifier(SETTINGS.supabase_url), RateLimiter(admin=None)
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield
    app.dependency_overrides.clear()
    del app.state.http


def test_parallel_users_on_shared_pool_never_see_each_others_data(overrides) -> None:
    with signed_in_users("isolation", 2) as (a, b):
        asyncio.run(_run(a, b))
