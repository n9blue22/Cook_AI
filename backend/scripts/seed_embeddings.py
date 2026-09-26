"""Sinh embedding bge-m3 cho các recipe chưa có embedding và ghi vào recipes.embedding.

embed_text = title + tên nguyên liệu đã map (VI và EN) + tên nguyên liệu gốc không map được.
Chạy từ thư mục backend, SAU seed_recipes: python -m scripts.seed_embeddings
Chạy lại an toàn — chỉ xử lý dòng embedding IS NULL (muốn embed lại hết: UPDATE recipes SET embedding = NULL).
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from postgrest import ReturnMethod
from tqdm import tqdm

from app.services.embedding.bge_m3 import BgeM3Provider
from scripts.seed_recipes import fetch_all_rows
from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

RECIPE_COLUMNS = "id,title,raw_ingredient_names,recipe_ingredients(ingredients(name_vi,name_en))"
WRITE_WORKERS = 8  # request update song song; ghi tuần tự chỉ ~2 recipe/s


def build_recipe_embed_text(recipe: dict) -> str:
    """Gộp tên món và tên nguyên liệu (cả VI lẫn EN, bỏ trùng, giữ thứ tự) thành text để embed."""
    names: list[str] = []
    for link in recipe["recipe_ingredients"]:
        names += [link["ingredients"]["name_vi"], link["ingredients"]["name_en"]]
    names += recipe["raw_ingredient_names"]
    unique_names = dict.fromkeys(name.strip() for name in names if name and name.strip())
    return f"{recipe['title']}. Nguyên liệu: {', '.join(unique_names)}"


def write_embeddings(recipe_ids: list[int], embeddings: list[list[float]]) -> None:
    """Update cột embedding từng recipe song song (PostgREST không update hàng loạt theo id khác nhau)."""
    thread_state = threading.local()

    def update_one(recipe_id: int, embedding: list[float]) -> None:
        # Mỗi thread một client: dùng chung 1 kết nối HTTP/2 giữa các thread gây httpx.ReadError trên Windows
        if not hasattr(thread_state, "client"):
            thread_state.client = create_admin_client()
        thread_state.client.table("recipes").update({"embedding": embedding}, returning=ReturnMethod.minimal).eq(
            "id", recipe_id,
        ).execute()

    with ThreadPoolExecutor(max_workers=WRITE_WORKERS) as pool:
        futures = [pool.submit(update_one, recipe_id, embedding) for recipe_id, embedding in zip(recipe_ids, embeddings)]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Ghi DB", unit="recipe"):
            future.result()  # ném lại lỗi của request nếu có


def seed_embeddings() -> None:
    """Đọc recipes chưa có embedding, encode bằng bge-m3, ghi embedding."""
    recipes = fetch_all_rows(create_admin_client(), "recipes", RECIPE_COLUMNS, null_column="embedding")
    if not recipes:
        logger.info("Mọi recipe đã có embedding")
        return
    texts = [build_recipe_embed_text(recipe) for recipe in recipes]
    logger.info("Cần embed %d recipe, ví dụ embed_text: %s", len(recipes), texts[0])
    embeddings = BgeM3Provider().encode(texts, show_progress_bar=True)
    write_embeddings([recipe["id"] for recipe in recipes], embeddings)
    logger.info("Đã ghi embedding cho %d recipe", len(recipes))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logger.setLevel(logging.INFO)
    seed_embeddings()
