"""Ảnh AI minh hoạ món (lazy): có trong Storage thì trả luôn, chưa có thì sinh bằng ImageGenProvider rồi cache."""

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
    """recipe_id không tồn tại hoặc chưa kiểm duyệt (RLS ẩn)."""


class DishImage(BaseModel):
    """Trả client; note luôn đi kèm để hiển thị nhãn ảnh AI."""

    recipe_id: int
    url: str
    cached: bool
    note: str = AI_IMAGE_NOTE


async def get_or_create_dish_image(
    recipe_id: int, client: AsyncClient, storage_admin: AsyncClient, image_gen: ImageGenProvider,
) -> DishImage:
    """Ảnh {recipe_id}.jpg trong bucket; chưa có → sinh + upload (ghi đè nếu 2 request cùng sinh)."""
    bucket = storage_admin.storage.from_(AI_DISH_BUCKET)
    path = f"{recipe_id}.jpg"
    if await bucket.exists(path):
        return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=True)
    image = await image_gen.generate_image(await build_dish_prompt(client, recipe_id))
    await bucket.upload(path, image.content, {"content-type": image.mime_type, "upsert": "true"})
    return DishImage(recipe_id=recipe_id, url=await bucket.get_public_url(path), cached=False)


async def build_dish_prompt(client: AsyncClient, recipe_id: int) -> str:
    """Prompt tiếng Anh từ tên món + tên EN nguyên liệu (FLUX hiểu tiếng Anh tốt hơn tên món tiếng Việt)."""
    rows = (
        await client.table("recipes").select("title,recipe_ingredients(ingredients(name_en))")
        .eq("id", recipe_id).execute()
    ).data
    if not rows:
        raise RecipeNotFoundError(f"Không có công thức {recipe_id}")
    names = [link["ingredients"]["name_en"] for link in rows[0]["recipe_ingredients"] if link["ingredients"]["name_en"]]
    return DISH_PROMPT.format(title=rows[0]["title"], ingredients=", ".join(names[:MAX_PROMPT_INGREDIENTS]))
