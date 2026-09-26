"""Seed recipes + recipe_ingredients + recipe_steps + recipe_allergens từ foodcom_filtered.csv và vifoodrec_processed.csv.

Chạy từ thư mục backend, SAU seed_ingredients + seed_allergens: python -m scripts.seed_recipes [--dry-run]
--dry-run: chỉ tính và in thống kê, không ghi DB.
Mỗi công thức ghi qua RPC insert_recipe (1 transaction). Chạy lại an toàn: trùng tên với dòng đã có thì bỏ qua.
"""

import argparse
import csv
import logging
from collections import Counter
from pathlib import Path

from supabase import Client

from app.services.ingredient_normalizer import CATALOG_COLUMNS, IngredientNormalizer, catalog_ingredient_from_row
from app.services.nutrition import Nutrition
from scripts.process_vifoodrec import read_servings_and_grams
from scripts.recipe_preparation import Catalog, DietFlags, PreparedRecipe, prepare_all
from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FOODCOM_CSV = DATA_DIR / "foodcom_filtered.csv"
VIFOODREC_CSV = DATA_DIR / "vifoodrec_processed.csv"
CSV_FIELD_SIZE_LIMIT = 2**31 - 1  # cột steps/description rất dài
PAGE_SIZE = 1000  # giới hạn mặc định của PostgREST mỗi request
GRAM_UNIT = "g"
PROGRESS_LOG_EVERY = 200


def fetch_all_rows(client: Client, table: str, columns: str, null_column: str | None = None) -> list[dict]:
    """Đọc hết bảng theo trang (PostgREST trả tối đa PAGE_SIZE dòng mỗi lần); null_column: chỉ lấy dòng cột đó NULL."""
    rows: list[dict] = []
    while True:
        query = client.table(table).select(columns)
        if null_column is not None:
            query = query.is_(null_column, "null")
        page = query.range(len(rows), len(rows) + PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows


def load_catalog(client: Client) -> Catalog:
    """Đọc ingredients, nutrition_facts, ingredient_allergens."""
    ingredient_rows = fetch_all_rows(client, "ingredients", f"{CATALOG_COLUMNS},is_vegetarian,is_vegan")
    fact_rows = fetch_all_rows(client, "nutrition_facts", "ingredient_id,kcal_100g,protein_g,carb_g,fat_g")
    allergens_by_ingredient: dict[int, set[int]] = {}
    for row in fetch_all_rows(client, "ingredient_allergens", "ingredient_id,allergen_id"):
        allergens_by_ingredient.setdefault(row["ingredient_id"], set()).add(row["allergen_id"])
    return Catalog(
        normalizer=IngredientNormalizer(catalog_ingredient_from_row(row) for row in ingredient_rows),
        diet_flags={row["id"]: DietFlags(row["is_vegetarian"], row["is_vegan"]) for row in ingredient_rows},
        facts={
            row["ingredient_id"]: Nutrition(row["kcal_100g"], row["protein_g"], row["carb_g"], row["fat_g"])
            for row in fact_rows
        },
        allergens_by_ingredient=allergens_by_ingredient,
        allergen_id_by_slug={row["slug"]: row["id"] for row in fetch_all_rows(client, "allergens", "id,slug")},
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Đọc CSV UTF-8 thành list dict theo header."""
    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def insert_recipe(client: Client, recipe: PreparedRecipe) -> None:
    """Ghi 1 công thức + bảng con qua RPC insert_recipe — lỗi thì rollback cả công thức, không để recipe mồ côi."""
    client.rpc("insert_recipe", {
        "recipe": {
            "title": recipe.title, "description": recipe.description, "servings": recipe.servings,
            "prep_minutes": recipe.prep_minutes, "diet_type": recipe.diet_type,
            "is_verified": recipe.is_verified, "source_url": recipe.source_url,
            "raw_ingredient_names": recipe.raw_ingredient_names,
        },
        "ingredients": [
            {"ingredient_id": ingredient_id, "amount": grams, "unit": GRAM_UNIT if grams else None}
            for ingredient_id, grams in recipe.grams_by_ingredient.items()
        ],
        "steps": [{"step_no": number, "instruction": step} for number, step in enumerate(recipe.steps, start=1)],
        "allergen_ids": sorted(recipe.allergen_ids),
    }).execute()


def print_stats(kept: list[PreparedRecipe], rejections: Counter, total: int) -> None:
    """In số giữ/loại, lý do loại, phân bố diet, độ phủ dinh dưỡng và dị ứng."""
    print(f"Tổng {total} công thức — giữ {len(kept)}, loại {sum(rejections.values())}")
    for reason, count in rejections.most_common():
        print(f"  loại vì {reason}: {count}")
    verified = sum(recipe.is_verified for recipe in kept)
    print(f"Giữ theo nguồn: ViFoodRec (verified) {verified}, Food.com {len(kept) - verified}")
    print(f"diet_type: {dict(Counter(recipe.diet_type for recipe in kept))}")
    print(f"Có dinh dưỡng/khẩu phần (có định lượng gram): {sum(recipe.nutrition is not None for recipe in kept)}")
    print(f"Có ít nhất 1 allergen: {sum(bool(recipe.allergen_ids) for recipe in kept)}")


def main() -> None:
    """Đọc CSV → map + phân loại → insert từng công thức (trừ khi --dry-run) → in thống kê."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ in thống kê, không ghi DB")
    dry_run = parser.parse_args().dry_run

    client = create_admin_client()
    existing_titles = {row["title"].lower() for row in fetch_all_rows(client, "recipes", "title")}
    rows = read_csv_rows(FOODCOM_CSV) + read_csv_rows(VIFOODREC_CSV)
    kept, rejections = prepare_all(rows, load_catalog(client), read_servings_and_grams(), existing_titles)
    if not dry_run:
        for count, recipe in enumerate(kept, start=1):
            insert_recipe(client, recipe)
            if count % PROGRESS_LOG_EVERY == 0:
                logger.info("Đã ghi %d/%d công thức", count, len(kept))
    print_stats(kept, rejections, len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
