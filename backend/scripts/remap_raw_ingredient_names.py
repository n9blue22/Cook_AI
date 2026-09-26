"""Map lại recipes.raw_ingredient_names theo catalog/normalizer hiện tại (sau khi thêm alias, từ mô tả cách cắt...).

Tên nay map được → thêm vào recipe_ingredients (không có lượng) + recipe_allergens, rồi bỏ khỏi raw_ingredient_names.
Embedding của recipe bị đổi đặt về NULL (embed_text gồm tên nguyên liệu) — recipe tạm vắng khỏi search_recipes
cho tới khi chạy seed_embeddings.
Chạy từ thư mục backend (chạy lại an toàn):
    python -m scripts.remap_raw_ingredient_names [--dry-run] && python -m scripts.seed_embeddings
"""

import argparse
from collections import Counter
from dataclasses import dataclass

from supabase import Client

from scripts.backfill_raw_ingredient_names import ingredient_ids_by_recipe
from scripts.recipe_preparation import Catalog, map_ingredients
from scripts.seed_recipes import fetch_all_rows, load_catalog
from scripts.supabase_admin import create_admin_client


@dataclass(frozen=True)
class Remap:
    """Thay đổi cho 1 recipe: nguyên liệu mới map được + tên còn lại không map được."""

    recipe_id: int
    mapped_names: list[str]
    new_ingredient_ids: set[int]
    remaining_raw_names: list[str]


def plan_remaps(client: Client, catalog: Catalog) -> list[Remap]:
    """Chạy lại map_ingredients (cùng luật lúc seed) trên tên gốc chưa map của mọi recipe."""
    existing_ids = ingredient_ids_by_recipe(client)
    remaps = []
    for row in fetch_all_rows(client, "recipes", "id,title,raw_ingredient_names"):
        raw_names = row["raw_ingredient_names"]
        if not raw_names:
            continue
        mapping = map_ingredients(raw_names, row["title"], {}, catalog)
        if len(mapping.unmatched) == len(raw_names):
            continue
        remaps.append(Remap(
            recipe_id=row["id"],
            mapped_names=[name for name in raw_names if name not in mapping.unmatched],
            new_ingredient_ids=set(mapping.grams_by_ingredient) - existing_ids.get(row["id"], set()),
            remaining_raw_names=mapping.unmatched,
        ))
    return remaps


def apply_remap(client: Client, remap: Remap, catalog: Catalog) -> None:
    """Ghi 1 recipe: recipe_ingredients + recipe_allergens của nguyên liệu mới, cập nhật raw names, bỏ embedding cũ."""
    if remap.new_ingredient_ids:
        client.table("recipe_ingredients").insert([
            {"recipe_id": remap.recipe_id, "ingredient_id": ingredient_id} for ingredient_id in remap.new_ingredient_ids
        ]).execute()
    allergen_ids = set().union(*(catalog.allergens_by_ingredient.get(i, set()) for i in remap.new_ingredient_ids))
    if allergen_ids:
        client.table("recipe_allergens").upsert(
            [{"recipe_id": remap.recipe_id, "allergen_id": allergen_id} for allergen_id in allergen_ids],
            ignore_duplicates=True,
        ).execute()
    client.table("recipes").update({"raw_ingredient_names": remap.remaining_raw_names, "embedding": None}).eq(
        "id", remap.recipe_id,
    ).execute()


def main() -> None:
    """In các tên nay map được (để soát trước), ghi DB trừ khi --dry-run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ in thống kê, không ghi DB")
    dry_run = parser.parse_args().dry_run

    client = create_admin_client()
    catalog = load_catalog(client)
    remaps = plan_remaps(client, catalog)
    for name, count in Counter(name.lower() for remap in remaps for name in remap.mapped_names).most_common():
        print(f"{count:4d}  {name}")
    if not dry_run:
        for remap in remaps:
            apply_remap(client, remap, catalog)
    print(f"Recipe {'sẽ ' if dry_run else 'đã '}cập nhật: {len(remaps)} — "
          f"thêm {sum(len(remap.new_ingredient_ids) for remap in remaps)} dòng recipe_ingredients")


if __name__ == "__main__":
    main()
