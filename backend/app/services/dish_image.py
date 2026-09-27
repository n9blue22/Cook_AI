"""Ảnh AI minh hoạ món (lazy): có trong Storage thì trả luôn, chưa có thì sinh bằng ImageGenProvider rồi cache."""

import re
import unicodedata
from collections.abc import Awaitable, Callable

from pydantic import BaseModel
from supabase import AsyncClient

from app.services.image_gen.provider import ImageGenProvider

AI_DISH_BUCKET = "ai-dish-images"  # khớp migration create_ai_dish_images_bucket
AI_IMAGE_NOTE = "Ảnh do AI tạo, chỉ mang tính minh hoạ"
DISH_PROMPT = (
    'Appetizing food photography of the finished dish "{title}", made with {ingredients}. '
    "Plated on a table, natural light, close-up, realistic, no text, no people."
)
MAX_PROMPT_INGREDIENTS = 8
MAX_DISPLAY_TITLE_CHARS = 120
# Từ được phép trong tên món AI chỉnh ngoài tên nguyên liệu: cách nấu + từ nối. Không có tên nguyên liệu nào ở đây.
COOKING_WORDS = frozenset(
    "nướng chiên rán xào luộc hấp kho rim om hầm nấu áp chảo quay rang ram cuốn trộn sốt xốt canh súp cháo gỏi nộm "
    "nhân nhồi nhanh với và cùng kiểu món".split()
)


class RecipeNotFoundError(Exception):
    """recipe_id không tồn tại."""


class DishImage(BaseModel):
    """Trả client; note luôn đi kèm để hiển thị nhãn ảnh AI."""

    recipe_id: int
    url: str
    cached: bool
    note: str = AI_IMAGE_NOTE


async def get_or_create_dish_image(
    recipe_id: int, display_title: str | None, admin: AsyncClient, image_gen: ImageGenProvider,
    before_generate: Callable[[], Awaitable[None]],
) -> DishImage:
    """Ảnh {recipe_id}.jpg trong bucket; chưa có → before_generate() (trừ quota) → sinh + upload.
    display_title = tên món client đang hiển thị (chỉ dùng khi qua pick_prompt_title)."""
    bucket = admin.storage.from_(AI_DISH_BUCKET)
    path = f"{recipe_id}.jpg"
    if await bucket.exists(path):
        return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=True)
    prompt = await build_dish_prompt(admin, recipe_id, display_title)  # recipe không tồn tại → 404 trước khi trừ quota
    await before_generate()
    image = await image_gen.generate_image(prompt)
    await bucket.upload(path, image.content, {"content-type": image.mime_type, "upsert": "true"})
    return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=False)


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
