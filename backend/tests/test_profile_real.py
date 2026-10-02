"""GET/PATCH /profile qua backend thật: JWT thật (Supabase ký ES256) → JwtVerifier + JWKS thật → DB bằng JWT user (RLS).
Tạo user bằng admin API và xoá sau khi chạy."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_jwt_verifier, get_rate_limiter, get_user_http
from app.core.config import get_settings
from app.main import app
from app.services.auth_tokens import JwtVerifier
from app.services.rate_limit import RateLimiter
from tests.real_users import fresh_user_http, signed_in_users

SETTINGS = get_settings()


@pytest.fixture(scope="module")
def access_token() -> Iterator[str]:
    with signed_in_users("profile", 1) as [headers]:
        yield headers["Authorization"].removeprefix("Bearer ")


@pytest.fixture
def client() -> TestClient:
    verifier, limiter = JwtVerifier(SETTINGS.supabase_url), RateLimiter(admin=None)
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_user_http] = fresh_user_http
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_profile_read_and_update_with_real_jwt(client: TestClient, access_token: str) -> None:
    auth = {"Authorization": f"Bearer {access_token}"}

    initial = client.get("/api/v1/profile", headers=auth)
    assert initial.status_code == 200
    assert initial.json() == {"diet_type": "omnivore", "daily_kcal_goal": None, "allergens": []}  # trigger tạo sẵn

    changes = {"diet_type": "vegetarian", "daily_kcal_goal": 1800, "allergens": ["peanut", "egg", "egg"]}
    updated = client.patch("/api/v1/profile", headers=auth, json=changes)
    assert updated.json() == {"diet_type": "vegetarian", "daily_kcal_goal": 1800, "allergens": ["egg", "peanut"]}

    partial = client.patch("/api/v1/profile", headers=auth, json={"allergens": []})  # chỉ đổi dị ứng
    assert partial.json() == {"diet_type": "vegetarian", "daily_kcal_goal": 1800, "allergens": []}


def test_profile_rejects_bad_input_and_missing_login(client: TestClient, access_token: str) -> None:
    auth = {"Authorization": f"Bearer {access_token}"}

    assert client.patch("/api/v1/profile", headers=auth, json={"allergens": ["eggs"]}).status_code == 422
    assert client.patch("/api/v1/profile", headers=auth, json={"daily_kcal_goal": 50}).status_code == 422
    assert client.patch("/api/v1/profile", headers=auth, json={"diet_type": "keto"}).status_code == 422
    assert client.get("/api/v1/profile").status_code == 401
    assert client.get("/api/v1/profile", headers={"Authorization": f"Bearer {access_token[:-6]}xxxxxx"}).status_code == 401
