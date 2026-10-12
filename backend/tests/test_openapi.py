"""OpenAPI: scheme Bearer cho Swagger (nút Authorize) mà vẫn giữ nguyên cách kiểm header của require_user."""

from types import SimpleNamespace

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.deps import get_jwt_verifier, require_user
from app.api.errors import UNAUTHENTICATED_MESSAGE
from app.core.config import get_settings
from app.main import create_app
from app.services.auth_tokens import CurrentUser


class RecordingVerifier:
    """Ghi lại token nhận được thay vì kiểm chữ ký thật."""

    def __init__(self) -> None:
        self.tokens: list[str] = []

    async def verify(self, token: str) -> SimpleNamespace:
        self.tokens.append(token)
        return SimpleNamespace(id="user-1")


@pytest.fixture
def probe() -> tuple[TestClient, RecordingVerifier]:
    app = create_app(get_settings())
    verifier = RecordingVerifier()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier

    async def whoami(user: CurrentUser = Depends(require_user)) -> dict[str, str]:
        return {"id": user.id}

    app.add_api_route("/probe", whoami)
    return TestClient(app), verifier


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer    ", "Basic abc", "Token abc", "bearer"])
def test_missing_or_malformed_bearer_gives_same_401(probe, header: str | None) -> None:
    client, verifier = probe
    headers = {} if header is None else {"Authorization": header}
    response = client.get("/probe", headers=headers)
    assert response.status_code == 401 and response.json() == {"detail": UNAUTHENTICATED_MESSAGE}
    assert response.headers["www-authenticate"] == "Bearer" and verifier.tokens == []


@pytest.mark.parametrize("header", ["Bearer tok", "bearer tok", "BEARER tok", "Bearer   tok  "])
def test_bearer_token_is_passed_trimmed_to_verifier(probe, header: str) -> None:
    client, verifier = probe
    assert client.get("/probe", headers={"Authorization": header}).json() == {"id": "user-1"}
    assert verifier.tokens == ["tok"]


def test_openapi_declares_bearer_on_protected_routes_only() -> None:
    schema = create_app(get_settings()).openapi()
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http", "scheme": "bearer", "description": "Access token lấy từ POST /api/v1/auth/login",
    }
    assert schema["paths"]["/api/v1/profile"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
    assert "security" not in schema["paths"]["/api/v1/health"]["get"]
