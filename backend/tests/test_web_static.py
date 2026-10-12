"""Web tĩnh cùng địa chỉ với API: fallback SPA chỉ cho đường dẫn không đuôi, /api/* và file thiếu → 404 JSON,
/docs, /openapi.json, /api/v1/health không bị mount "/" che, cache + gzip đúng loại file."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rate_limiter
from app.api.v1 import health
from app.core.config import get_settings
from app.core.web_static import CACHE_IMMUTABLE, CACHE_REVALIDATE, mount_web
from app.main import create_app
from app.services.rate_limit import RateLimiter

INDEX_HTML = "<!doctype html><title>Chef AI</title><div id=root></div>"
BUNDLE_PATH = "_expo/static/js/web/entry-3d5094a3.js"
BUNDLE_JS = "console.log('chef');" * 500  # ~10 KB: vượt ngưỡng nén
NOT_FOUND = {"detail": "Not Found"}


def _write(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _write(tmp_path, "index.html", INDEX_HTML)
    _write(tmp_path, BUNDLE_PATH, BUNDLE_JS)
    _write(tmp_path, "favicon.ico", "ico")
    app = create_app(get_settings())
    mount_web(app, tmp_path)
    limiter = RateLimiter(admin=None)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    async def supabase_ok(settings: object) -> bool:
        return True

    monkeypatch.setattr(health, "is_supabase_reachable", supabase_ok)  # health không gọi mạng
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/recipe/123", "/login", "/reset-password", "/cook"])
def test_spa_routes_without_extension_serve_index(client: TestClient, path: str) -> None:
    response = client.get(path, params={"verified": "1"})
    assert response.status_code == 200 and response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == CACHE_REVALIDATE


@pytest.mark.parametrize("path", ["/api", "/api/v1/khong-co", "/api/v1/recipe/123", "/api/v2/pantry"])
def test_unknown_api_paths_return_json_404_not_index(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404 and response.json() == NOT_FOUND


@pytest.mark.parametrize("path", ["/_expo/static/js/web/khong-co.js", "/styles.css", "/assets/logo.png", "/a/b.map"])
def test_missing_files_with_extension_return_404_not_index(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 404 and response.json() == NOT_FOUND


def test_hashed_bundle_is_immutable_and_gzipped(client: TestClient) -> None:
    response = client.get(f"/{BUNDLE_PATH}", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200 and response.text == BUNDLE_JS  # httpx tự giải nén
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == CACHE_IMMUTABLE


def test_unhashed_file_revalidates(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200 and response.headers["cache-control"] == CACHE_REVALIDATE


def test_docs_openapi_and_health_are_not_shadowed(client: TestClient) -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200 and "swagger-ui" in docs.text and INDEX_HTML not in docs.text
    openapi = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert openapi.status_code == 200 and openapi.json()["info"]["title"] == "Chef AI API"
    assert "content-encoding" not in openapi.headers  # API không nén
    health_response = client.get("/api/v1/health")
    assert health_response.status_code == 200 and health_response.json()["supabase"] == "ok"


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_non_get_on_unknown_api_path_is_still_json_404(client: TestClient, method: str) -> None:
    response = client.request(method, "/api/v1/khong-co")
    assert response.status_code == 404 and response.json() == NOT_FOUND


def test_without_build_nothing_is_mounted(tmp_path: Path) -> None:
    app = create_app(get_settings())
    mount_web(app, tmp_path / "khong-co-dist")
    response = TestClient(app).get("/recipe/123")
    assert response.status_code == 404 and response.json() == NOT_FOUND
