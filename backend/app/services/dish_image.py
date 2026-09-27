"""Ảnh AI minh hoạ món (lazy): có trong Storage thì trả luôn, chưa có thì sinh bằng ImageGenProvider rồi cache."""

import re
import time
import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel
from supabase import AsyncClient

from app.services.image_gen.provider import ImageGenProvider
from app.services.rate_limit import RateLimiter

AI_DISH_BUCKET = "ai-dish-images"  # khớp migration create_ai_dish_images_bucket
AI_IMAGE_NOTE = "Ảnh do AI tạo, chỉ mang tính minh hoạ"
DISH_PROMPT = (
    'Appetizing food photography of the finished dish "{title}", made with {ingredients}. '
    "Plated on a table, natural light, close-up, realistic, no text, no people."
)
MAX_PROMPT_INGREDIENTS = 8
QUOTA_POLICY = "dish_image_generate"
MAX_DISPLAY_TITLE_CHARS = 120
# Từ được phép trong tên món AI chỉnh ngoài tên nguyên liệu: cách nấu + từ nối. Không có tên nguyên liệu nào ở đây.
COOKING_WORDS = frozenset(
    "nướng chiên rán xào luộc hấp kho rim om hầm nấu áp chảo quay rang ram cuốn trộn sốt xốt canh súp cháo gỏi nộm "
    "nhân nhồi nhanh với và cùng kiểu món".split()
)


class RecipeNotFoundError(Exception):
    """recipe_id không tồn tại."""


@dataclass(frozen=True)
class DishImageRequest:
    """Yêu cầu ảnh của 1 user; regenerate = "Tạo lại": luôn sinh bản riêng, không đụng ảnh dùng chung."""

    recipe_id: int
    user_id: str
    display_title: str | None  # tên món client đang hiển thị (chỉ dùng khi qua pick_prompt_title)
    regenerate: bool = False


class DishImage(BaseModel):
    """Trả client; note luôn đi kèm để hiển thị nhãn ảnh AI."""

    recipe_id: int
    url: str
    cached: bool
    note: str = AI_IMAGE_NOTE


async def get_or_create_dish_image(
    request: DishImageRequest, admin: AsyncClient, image_gen: ImageGenProvider, limiter: RateLimiter,
) -> DishImage:
    """Ảnh dùng chung {recipe_id}.jpg (có thì trả luôn, không tốn quota); "Tạo lại" → bản riêng của user.
    Quota: kiểm tra còn lượt trước khi sinh, chỉ trừ SAU khi Cloudflare + Storage thành công."""
    recipe_id = request.recipe_id
    bucket = admin.storage.from_(AI_DISH_BUCKET)
    path = dish_image_path(request)
    if not request.regenerate and await bucket.exists(path):
        return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=True)
    prompt = await build_dish_prompt(admin, recipe_id, request.display_title)  # không có recipe → 404, chưa đụng quota
    await limiter.ensure_daily_available(QUOTA_POLICY, request.user_id)
    image = await image_gen.generate_image(prompt)
    await bucket.upload(path, image.content, {"content-type": image.mime_type, "upsert": "true"})
    await limiter.record_daily_after_success(QUOTA_POLICY, request.user_id)
    return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=False)


def dish_image_path(request: DishImageRequest) -> str:
    """Ảnh dùng chung theo recipe_id; "Tạo lại" → {recipe_id}-{user_id}-{ms}.jpg để không ghi đè ảnh người khác."""
    if not request.regenerate:
        return f"{request.recipe_id}.jpg"
    return f"{request.recipe_id}-{request.user_id}-{time.time_ns() // 1_000_000}.jpg"


async def build_dish_prompt(admin: AsyncClient, recipe_id: int, display_title: str | None) -> str:
    """Prompt từ tên món (tên đang hiển thị nếu hợp lệ, không thì tên gốc) + tên EN nguyên liệu.
    Đọc bằng admin (bỏ qua RLS is_verified) như search_recipes: món chưa verified vẫn được /recipes/suggest trả về."""
    rows = (
        await admin.table("recipes").select("title,recipe_ingredients(ingredients(name_en,name_vi))")
        .eq("id", recipe_id).execute()
    ).data
    if not rows:
        raise RecipeNotFoundError(f"Không có công thức {recipe_id}")
    ingredients = [link["ingredients"] for link in rows[0]["recipe_ingredients"]]
    title = pick_prompt_title(display_title, rows[0]["title"], [i["name_vi"] for i in ingredients if i["name_vi"]])
    names_en = [i["name_en"] for i in ingredients if i["name_en"]]
    return DISH_PROMPT.format(title=title, ingredients=", ".join(names_en[:MAX_PROMPT_INGREDIENTS]))


def pick_prompt_title(display_title: str | None, db_title: str, ingredient_names_vi: list[str]) -> str:
    """Tên client gửi chỉ được dùng khi MỌI từ đều thuộc tên nguyên liệu / tên gốc / COOKING_WORDS và có ít nhất
    1 từ nguyên liệu hoặc tên gốc — chặn tên bịa (ảnh cache theo recipe_id dùng chung mọi user). Không đạt → tên gốc."""
    if not display_title:
        return db_title
    known_words = _words(" ".join(ingredient_names_vi)) | _words(db_title)
    title_words = _words(display_title)
    if title_words <= known_words | COOKING_WORDS and title_words & known_words:
        return " ".join(re.findall(r"\w+", unicodedata.normalize("NFC", display_title)))  # bỏ dấu câu khỏi prompt
    return db_title


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", unicodedata.normalize("NFC", text).lower()))
