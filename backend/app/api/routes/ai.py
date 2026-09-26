"""Endpoint AI (feature-spec mục 6): nhận diện ảnh, gợi ý công thức, ảnh minh hoạ món — logic nằm ở services/."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from supabase import AsyncClient

from app.services.dish_image import DishImage, RecipeNotFoundError, get_or_create_dish_image
from app.services.embedding.provider import EmbeddingProvider
from app.services.image_gen.provider import ImageGenProvider, ImageGenUnavailableError
from app.services.ingredient_normalizer import load_ingredient_catalog
from app.services.llm.provider import LLMProvider
from app.services.pipeline import (
    NoUsableIngredientsError,
    RecognizedIngredients,
    SuggestedRecipe,
    SuggestRequest,
    recognize_ingredients,
    suggest_recipes,
)
from app.services.upload_image import (
    MAX_UPLOAD_BYTES,
    VISION_MIME,
    ImageTooLargeError,
    InvalidImageError,
    prepare_image_for_vision,
)
from app.services.vision.provider import VisionProvider, VisionUnavailableError

logger = logging.getLogger(__name__)

DietType = Literal["omnivore", "vegetarian", "vegan"]
# Phải khớp bảng allergens (test đối chiếu DB): slug lạ bị từ chối thay vì âm thầm không lọc dị ứng.
AllergenSlug = Literal["shellfish", "molluscs", "fish", "egg", "dairy", "peanut", "tree_nuts", "soy", "wheat", "sesame"]
MAX_SERVINGS = 20

# Lỗi nghiệp vụ → HTTP. Message None = trả str(lỗi) (đã viết cho user); 5xx dùng câu cố định, không lộ chi tiết.
ERROR_RESPONSES: dict[type[Exception], tuple[int, str | None]] = {
    ImageTooLargeError: (413, None),
    InvalidImageError: (415, None),
    NoUsableIngredientsError: (422, None),
    RecipeNotFoundError: (404, None),
    VisionUnavailableError: (503, "Không nhận diện được ảnh, thử lại"),
    ImageGenUnavailableError: (503, "Chưa tạo được ảnh minh hoạ, thử lại sau"),
}

router = APIRouter(tags=["ai"])


@dataclass(frozen=True)
class AiServices:
    """Client + provider dựng 1 lần lúc khởi động (main.lifespan), dùng chung mọi request."""

    supabase: AsyncClient
    storage_admin: AsyncClient
    vision: VisionProvider
    embedder: EmbeddingProvider
    llm: LLMProvider
    image_gen: ImageGenProvider


def get_ai_services(request: Request) -> AiServices:
    """Dependency lấy AiServices từ app.state (test thay bằng dependency_overrides)."""
    return request.app.state.ai_services


class SuggestBody(BaseModel):
    """Body /recipes/suggest (feature-spec mục 6)."""

    ingredient_ids: list[int]
    diet_type: DietType
    allergens: list[AllergenSlug] = []
    servings: int | None = Field(default=None, ge=1, le=MAX_SERVINGS)


@router.post("/recognize", response_model=RecognizedIngredients)
async def recognize(
    image: UploadFile = File(...), services: AiServices = Depends(get_ai_services),
) -> RecognizedIngredients:
    """Ảnh (multipart, field "image") → nguyên liệu chắc chắn + chưa chắc để user xác nhận."""
    prepared = await asyncio.to_thread(prepare_image_for_vision, await image.read(MAX_UPLOAD_BYTES + 1))
    catalog = await load_ingredient_catalog(services.supabase)
    return await recognize_ingredients(prepared, VISION_MIME, services.vision, catalog)


@router.post("/recipes/suggest", response_model=list[SuggestedRecipe])
async def suggest(body: SuggestBody, services: AiServices = Depends(get_ai_services)) -> list[SuggestedRecipe]:
    """Nguyên liệu đã xác nhận + diet + dị ứng → tối đa 5 công thức (adapted hoặc original)."""
    request = SuggestRequest(**body.model_dump())
    return await suggest_recipes(request, services.supabase, services.embedder, services.llm)


@router.post("/recipes/{recipe_id}/image", response_model=DishImage)
async def dish_image(recipe_id: int, services: AiServices = Depends(get_ai_services)) -> DishImage:
    """Ảnh AI minh hoạ món — lazy, cache trong Storage, luôn kèm note "ảnh do AI tạo"."""
    return await get_or_create_dish_image(recipe_id, services.supabase, services.storage_admin, services.image_gen)


def register_ai_error_handlers(app: FastAPI) -> None:
    """Gắn handler cho từng lỗi nghiệp vụ trong ERROR_RESPONSES."""
    for error_type, (status_code, public_message) in ERROR_RESPONSES.items():
        app.add_exception_handler(error_type, _error_handler(status_code, public_message))


def _error_handler(
    status_code: int, public_message: str | None,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle(request: Request, error: Exception) -> JSONResponse:
        if status_code >= 500:
            logger.warning("%s %s → %d: %s", request.method, request.url.path, status_code, error)
        return JSONResponse(status_code=status_code, content={"detail": public_message or str(error)})
    return handle
