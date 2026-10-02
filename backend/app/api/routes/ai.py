"""Endpoint AI (feature-spec mục 6): nhận diện ảnh, gợi ý công thức, ảnh minh hoạ món — logic nằm ở services/."""

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from supabase import AsyncClient

from app.api.deps import get_rate_limiter, limit_user
from app.services.auth_tokens import CurrentUser
from app.services.diet_types import AllergenSlug, DietType
from app.services.dish_image import (
    MAX_DISPLAY_TITLE_CHARS,
    DishImage,
    DishImageRequest,
    RecipeNotFoundError,
    get_or_create_dish_image,
)
from app.services.embedding.provider import EmbeddingProvider
from app.services.image_gen.provider import ImageGenProvider, ImageGenUnavailableError
from app.services.ingredient_normalizer import IngredientCatalogCache
from app.services.llm.provider import LLMProvider
from app.services.rate_limit import RateLimiter
from app.services.pipeline import (
    NoUsableIngredientsError,
    RecognizedIngredients,
    SuggestRequest,
    recognize_ingredients,
    suggest_recipes,
)
from app.services.recipe_results import SuggestedRecipe
from app.services.upload_image import (
    MAX_UPLOAD_BYTES,
    VISION_MIME,
    ImageTooLargeError,
    InvalidImageError,
    prepare_image_for_vision,
)
from app.services.vision.provider import VisionProvider, VisionUnavailableError

logger = logging.getLogger(__name__)

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
# Cả 3 endpoint tốn quota AI thật → bắt buộc đăng nhập + rate limit theo user (services/rate_limit.py).
recognize_user = limit_user("recognize", consume_daily=True)
suggest_user = limit_user("suggest")  # quota ngày: kiểm trước, chỉ trừ khi gợi ý thành công (xem suggest)
dish_image_user = limit_user("dish_image")


@dataclass(frozen=True)
class AiServices:
    """Client + provider dựng 1 lần lúc khởi động (main.lifespan), dùng chung mọi request."""

    supabase: AsyncClient
    admin: AsyncClient  # secret key: Storage + RPC nội bộ
    vision: VisionProvider
    embedder: EmbeddingProvider
    llm: LLMProvider
    image_gen: ImageGenProvider
    catalog: IngredientCatalogCache  # danh mục ingredients trong RAM, hết hạn sau vài phút


def get_ai_services(request: Request) -> AiServices:
    """Dependency lấy AiServices từ app.state (test thay bằng dependency_overrides)."""
    return request.app.state.ai_services


class SuggestBody(BaseModel):
    """Body /recipes/suggest (feature-spec mục 6)."""

    ingredient_ids: list[int]
    diet_type: DietType
    allergens: list[AllergenSlug] = []
    servings: int | None = Field(default=None, ge=1, le=MAX_SERVINGS)


class DishImageBody(BaseModel):
    """Body /recipes/{id}/image: tên món đang hiển thị (tên AI chỉnh) — backend tự kiểm tra trước khi dùng."""

    title: str | None = Field(default=None, max_length=MAX_DISPLAY_TITLE_CHARS)
    regenerate: bool = False  # "Tạo lại": sinh bản riêng của user, tốn quota như lần đầu


@router.post("/recognize", response_model=RecognizedIngredients)
async def recognize(
    image: UploadFile = File(...), services: AiServices = Depends(get_ai_services),
    _user: CurrentUser = Depends(recognize_user),
) -> RecognizedIngredients:
    """Ảnh (multipart, field "image") → nguyên liệu chắc chắn + chưa chắc để user xác nhận."""
    prepared = await asyncio.to_thread(prepare_image_for_vision, await image.read(MAX_UPLOAD_BYTES + 1))
    catalog = await services.catalog.get()
    return await recognize_ingredients(prepared, VISION_MIME, services.vision, catalog)


@router.post("/recipes/suggest", response_model=list[SuggestedRecipe])
async def suggest(
    body: SuggestBody, services: AiServices = Depends(get_ai_services), user: CurrentUser = Depends(suggest_user),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> list[SuggestedRecipe]:
    """Nguyên liệu đã xác nhận + diet + dị ứng → tối đa 5 công thức (adapted hoặc original).
    Quota ngày: kiểm (song song với embed, trước khi tìm) rồi chỉ trừ khi trả kết quả thành công, giống ảnh AI."""
    request = SuggestRequest(**body.model_dump())
    quota_check = functools.partial(limiter.ensure_daily_available, "suggest", user.id)
    recipes = await suggest_recipes(
        request, services.catalog, services.supabase, services.admin, services.embedder, services.llm, quota_check,
    )
    await limiter.record_daily_after_success("suggest", user.id)
    return recipes


@router.post("/recipes/{recipe_id}/image", response_model=DishImage)
async def dish_image(
    recipe_id: int, body: DishImageBody | None = None, services: AiServices = Depends(get_ai_services),
    user: CurrentUser = Depends(dish_image_user), limiter: RateLimiter = Depends(get_rate_limiter),
) -> DishImage:
    """Ảnh AI minh hoạ món — lazy, cache trong Storage, luôn kèm note "ảnh do AI tạo".
    Quota ngày chỉ bị trừ khi sinh ảnh mới thành công (lấy ảnh đã cache thì không)."""
    body = body or DishImageBody()
    request = DishImageRequest(recipe_id, user.id, body.title, body.regenerate)
    return await get_or_create_dish_image(request, services.admin, services.image_gen, limiter)


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
