"""Endpoint AI: upload ảnh (cỡ, định dạng, resize), map lỗi → HTTP, validate body, cache ảnh AI. Provider giả."""

import io
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import ai
from app.api.routes.ai import AiServices, get_ai_services
from app.main import app
from app.services import dish_image
from app.services.image_gen.provider import GeneratedImage, ImageGenProvider, ImageGenUnavailableError
from app.services.ingredient_matching import CatalogIngredient
from app.services.upload_image import MAX_SIDE_PX, MAX_UPLOAD_BYTES
from app.services.vision.provider import Detected, VisionProvider, VisionUnavailableError

CHICKEN_ID = 93
CATALOG = [CatalogIngredient(id=CHICKEN_ID, name_vi="Ức gà", name_en="Chicken breast")]


class FakeVision(VisionProvider):
    def __init__(self, output: Detected | Exception) -> None:
        self.output = output
        self.received: bytes | None = None

    async def detect_ingredients(self, image: bytes, mime_type: str) -> Detected:
        self.received = image
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class FakeImageGen(ImageGenProvider):
    def __init__(self, error: Exception | None = None) -> None:
        self.error, self.calls = error, 0

    async def generate_image(self, prompt: str) -> GeneratedImage:
        self.calls += 1
        if self.error:
            raise self.error
        return GeneratedImage(content=b"jpeg", mime_type="image/jpeg")


class FakeBucket:
    def __init__(self, has_file: bool) -> None:
        self.has_file, self.uploads = has_file, []

    async def exists(self, path: str) -> bool:
        return self.has_file

    async def upload(self, path: str, content: bytes, options: dict) -> None:
        self.uploads.append(path)

    async def get_public_url(self, path: str) -> str:
        return f"https://cdn/{path}"


class FakeStorageClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.storage = self
        self.bucket = bucket

    def from_(self, name: str) -> FakeBucket:
        return self.bucket


def client_with(vision: VisionProvider | None = None, image_gen: ImageGenProvider | None = None,
                bucket: FakeBucket | None = None) -> TestClient:
    services = AiServices(
        supabase=None, storage_admin=FakeStorageClient(bucket or FakeBucket(False)), vision=vision,
        embedder=None, llm=None, image_gen=image_gen,
    )
    app.dependency_overrides[get_ai_services] = lambda: services
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_db(monkeypatch: pytest.MonkeyPatch):
    async def fake_catalog(client):
        return CATALOG

    async def fake_prompt(client, recipe_id):
        return "prompt"

    monkeypatch.setattr(ai, "load_ingredient_catalog", fake_catalog)
    monkeypatch.setattr(dish_image, "build_dish_prompt", fake_prompt)
    yield
    app.dependency_overrides.clear()


def png_bytes(width: int = 64, height: int = 48) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(output, format="PNG")
    return output.getvalue()


def post_image(client: TestClient, data: bytes):
    return client.post("/api/v1/recognize", files={"image": ("photo.png", data, "image/png")})


def test_recognize_resizes_before_vision_and_maps_ingredients() -> None:
    vision = FakeVision(Detected(ingredients=["ức gà"], uncertain=[]))
    response = post_image(client_with(vision=vision), png_bytes(3000, 2000))

    assert response.status_code == 200 and response.json()["accepted_ids"] == [CHICKEN_ID]
    assert max(Image.open(io.BytesIO(vision.received)).size) == MAX_SIDE_PX


def test_recognize_distinguishes_vision_error_from_no_food() -> None:
    failed = post_image(client_with(vision=FakeVision(VisionUnavailableError("timeout"))), png_bytes())
    no_food = post_image(client_with(vision=FakeVision(Detected(ingredients=[], uncertain=[]))), png_bytes())

    assert failed.status_code == 503 and failed.json()["detail"] == "Không nhận diện được ảnh, thử lại"
    assert no_food.status_code == 422


def test_recognize_rejects_non_image_and_oversized_upload() -> None:
    client = client_with(vision=FakeVision(Detected(ingredients=["ức gà"], uncertain=[])))

    assert post_image(client, b"not an image").status_code == 415
    assert post_image(client, b"0" * (MAX_UPLOAD_BYTES + 1)).status_code == 413


def test_suggest_rejects_unknown_allergen_slug_instead_of_silently_not_filtering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received = []

    async def fake_suggest(request, client, embedder, llm):
        received.append(request)
        return []

    monkeypatch.setattr(ai, "suggest_recipes", fake_suggest)
    client = client_with()
    body = {"ingredient_ids": [CHICKEN_ID], "diet_type": "omnivore", "allergens": ["egg"]}

    assert client.post("/api/v1/recipes/suggest", json={**body, "allergens": ["eggs"]}).status_code == 422
    assert client.post("/api/v1/recipes/suggest", json={**body, "diet_type": "keto"}).status_code == 422
    assert client.post("/api/v1/recipes/suggest", json=body).status_code == 200
    assert [(r.ingredient_ids, r.allergens) for r in received] == [([CHICKEN_ID], ["egg"])]


def test_dish_image_generates_once_then_serves_cache_with_ai_note() -> None:
    image_gen = FakeImageGen()
    fresh = client_with(image_gen=image_gen, bucket=FakeBucket(has_file=False)).post("/api/v1/recipes/7/image")
    cached = client_with(image_gen=image_gen, bucket=FakeBucket(has_file=True)).post("/api/v1/recipes/7/image")

    assert fresh.json() == {"recipe_id": 7, "url": "https://cdn/7.jpg", "cached": False, "note": dish_image.AI_IMAGE_NOTE}
    assert cached.json()["cached"] is True
    assert image_gen.calls == 1  # bản cache không gọi model


def test_dish_image_errors_map_to_http(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = client_with(image_gen=FakeImageGen(ImageGenUnavailableError("429")))
    assert failing.post("/api/v1/recipes/7/image").status_code == 503

    async def missing_recipe(client, recipe_id):
        raise dish_image.RecipeNotFoundError("Không có công thức 999")

    monkeypatch.setattr(dish_image, "build_dish_prompt", missing_recipe)
    assert client_with(image_gen=FakeImageGen()).post("/api/v1/recipes/999/image").status_code == 404


def test_allergen_slugs_match_real_allergens_table() -> None:
    from scripts.supabase_admin import create_admin_client

    rows = create_admin_client().table("allergens").select("slug").execute().data
    assert set(get_args(ai.AllergenSlug)) == {row["slug"] for row in rows}
