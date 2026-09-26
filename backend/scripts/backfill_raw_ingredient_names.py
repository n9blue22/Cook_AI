"""Backfill recipes.raw_ingredient_names cho công thức đã seed trước khi có cột này (không seed lại).

Chạy lại pipeline map trên CSV gốc, đối chiếu tập ingredient_id với recipe_ingredients trong DB; chỉ ghi khi khớp
(tức phần tên không map được tính ra đúng là phần đã bị bỏ lúc seed).
Chạy từ thư mục backend: python -m scripts.backfill_raw_ingredient_names [--dry-run]  (chạy lại an toàn)
"""

import argparse
import logging

from supabase import Client

from scripts.process_vifoodrec import read_servings_and_grams
from scripts.recipe_preparation import PreparedRecipe, prepare_recipe
from scripts.seed_recipes import FOODCOM_CSV, VIFOODREC_CSV, fetch_all_rows, load_catalog, read_csv_rows
from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

PROGRESS_LOG_EVERY = 500


def ingredient_ids_by_recipe(client: Client) -> dict[int, set[int]]:
    """recipe_id → tập ingredient_id đang có trong recipe_ingredients."""
    ids: dict[int, set[int]] = {}
    for row in fetch_all_rows(client, "recipe_ingredients", "recipe_id,ingredient_id"):
        ids.setdefault(row["recipe_id"], set()).add(row["ingredient_id"])
    return ids


def rebuild_prepared_by_recipe_id(client: Client) -> dict[int, PreparedRecipe]:
    """Ghép mỗi recipe trong DB với dòng CSV đã sinh ra nó (cùng thứ tự + luật trùng tên như lúc seed)."""
    recipe_by_title = {row["title"].lower(): row for row in fetch_all_rows(client, "recipes", "id,title,is_verified")}
    catalog, extras = load_catalog(client), read_servings_and_grams()
    prepared_by_id: dict[int, PreparedRecipe] = {}
    for row in read_csv_rows(FOODCOM_CSV) + read_csv_rows(VIFOODREC_CSV):
        db_row = recipe_by_title.get(row["name"].strip().lower())
        if db_row is None or db_row["id"] in prepared_by_id:
            continue
        prepared = prepare_recipe(row, catalog, extras)
        if isinstance(prepared, PreparedRecipe) and prepared.is_verified == db_row["is_verified"]:
            prepared_by_id[db_row["id"]] = prepared
    return prepared_by_id


def main() -> None:
    """Tính tên không map được cho từng recipe, đối chiếu với DB, ghi (trừ khi --dry-run), in thống kê."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ in thống kê, không ghi DB")
    dry_run = parser.parse_args().dry_run

    client = create_admin_client()
    db_ingredients = ingredient_ids_by_recipe(client)
    prepared_by_id = rebuild_prepared_by_recipe_id(client)
    total = len(fetch_all_rows(client, "recipes", "id"))
    consistent = {
        recipe_id: prepared for recipe_id, prepared in prepared_by_id.items()
        if set(prepared.grams_by_ingredient) == db_ingredients.get(recipe_id, set())
    }
    to_write = {recipe_id: prepared for recipe_id, prepared in consistent.items() if prepared.raw_ingredient_names}
    if not dry_run:
        for count, (recipe_id, prepared) in enumerate(to_write.items(), start=1):
            client.table("recipes").update({"raw_ingredient_names": prepared.raw_ingredient_names}).eq(
                "id", recipe_id,
            ).execute()
            if count % PROGRESS_LOG_EVERY == 0:
                logger.info("Đã ghi %d/%d", count, len(to_write))
    print(f"Recipe trong DB: {total} — ghép được với CSV: {len(prepared_by_id)}")
    print(f"  khớp recipe_ingredients: {len(consistent)} — lệch (KHÔNG ghi): {len(prepared_by_id) - len(consistent)}")
    print(f"  có tên không map được → {'sẽ ' if dry_run else 'đã '}ghi: {len(to_write)}")
    print(f"  tổng số tên không map được: {sum(len(p.raw_ingredient_names) for p in to_write.values())}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logger.setLevel(logging.INFO)
    main()
