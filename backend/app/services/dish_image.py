"""Ảnh AI minh hoạ món (lazy): có trong Storage thì trả luôn, chưa có thì sinh bằng ImageGenProvider rồi cache."""

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


class RecipeNotFoundError(Exception):
    """recipe_id không tồn tại."""


class DishImage(BaseModel):
    """Trả client; note luôn đi kèm để hiển thị nhãn ảnh AI."""

    recipe_id: int
    url: str
    cached: bool
    note: str = AI_IMAGE_NOTE


async def get_or_create_dish_image(
    recipe_id: int, admin: AsyncClient, image_gen: ImageGenProvider,
    before_generate: Callable[[], Awaitable[None]],
) -> DishImage:
    """Ảnh {recipe_id}.jpg trong bucket; chưa có → before_generate() (trừ quota) → sinh + upload."""
    bucket = admin.storage.from_(AI_DISH_BUCKET)
    path = f"{recipe_id}.jpg"
    if await bucket.exists(path):
        return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=True)
    prompt = await build_dish_prompt(admin, recipe_id)  # recipe không tồn tại → 404 trước khi trừ quota
    await before_generate()
    image = await image_gen.generate_image(prompt)
    await bucket.upload(path, image.content, {"content-type": image.mime_type, "upsert": "true"})
    return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=False)


async def build_dish_prompt(admin: AsyncClient, recipe_id: int) -> str:
    """Prompt tiếng Anh từ tên món + tên EN nguyên liệu (FLUX hiểu tiếng Anh tốt hơn tên món tiếng Việt).
    Đọc bằng admin (bỏ qua RLS is_verified) như search_recipes: món chưa verified vẫn được /recipes/suggest trả về."""
    rows = (
        await admin.table("recipes").select("title,recipe_ingredients(ingredients(name_en))")
        .eq("id", recipe_id).execute()
    ).data
    if not rows:
        raise RecipeNotFoundError(f"Không có công thức {recipe_id}")
    names = [link["ingredients"]["name_en"] for link in rows[0]["recipe_ingredients"] if link["ingredients"]["name_en"]]
    return DISH_PROMPT.format(title=rows[0]["title"], ingredients=", ".join(names[:MAX_PROMPT_INGREDIENTS]))
