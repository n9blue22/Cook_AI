"""Seed ingredient_allergens từ data/ingredient_allergens.csv (name_vi, allergens dạng "slug1|slug2").

Chạy từ thư mục backend, SAU seed_ingredients và migration create_ingredient_allergens:
python -m scripts.seed_allergens  (chạy lại an toàn — upsert theo khoá chính)
"""

import logging
from pathlib import Path

from scripts.seed_ingredients import read_csv_rows
from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

INGREDIENT_ALLERGENS_CSV = Path(__file__).resolve().parents[1] / "data" / "ingredient_allergens.csv"
SLUG_SEPARATOR = "|"


def build_ingredient_allergen_rows(
    csv_rows: list[dict[str, str]], ingredient_ids: dict[str, int], allergen_ids: dict[str, int],
) -> list[dict[str, int]]:
    """Dòng CSV → dòng ingredient_allergens; tên/slug không tồn tại thì báo lỗi, không bỏ qua âm thầm."""
    rows = []
    for csv_row in csv_rows:
        ingredient_id = ingredient_ids.get(csv_row["name_vi"].lower())
        if ingredient_id is None:
            raise ValueError(f"Nguyên liệu '{csv_row['name_vi']}' chưa có trong bảng ingredients")
        for slug in csv_row["allergens"].split(SLUG_SEPARATOR):
            if slug not in allergen_ids:
                raise ValueError(f"{csv_row['name_vi']}: allergen '{slug}' chưa có trong bảng allergens")
            rows.append({"ingredient_id": ingredient_id, "allergen_id": allergen_ids[slug]})
    return rows


def seed_allergens() -> None:
    """Upsert toàn bộ gán dị ứng cho nguyên liệu."""
    client = create_admin_client()
    ingredient_ids = {
        row["name_vi"].lower(): row["id"] for row in client.table("ingredients").select("id,name_vi").execute().data
    }
    allergen_ids = {row["slug"]: row["id"] for row in client.table("allergens").select("id,slug").execute().data}
    rows = build_ingredient_allergen_rows(read_csv_rows(INGREDIENT_ALLERGENS_CSV), ingredient_ids, allergen_ids)
    client.table("ingredient_allergens").upsert(rows, on_conflict="ingredient_id,allergen_id").execute()
    logger.info("Đã upsert %d dòng ingredient_allergens", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_allergens()
