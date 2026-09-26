"""Chuẩn hoá 1 dòng công thức (format foodcom_filtered.csv) thành bản ghi seed: map nguyên liệu, diet, dị ứng, dinh dưỡng.

Thuần logic, không chạm DB — seed_recipes.py lo phần đọc/ghi.
"""

import ast
from collections import Counter
from dataclasses import dataclass

from app.services.ingredient_matching import strip_diacritics
from app.services.ingredient_normalizer import IngredientNormalizer, MatchStatus, clean_ingredient_name
from app.services.nutrition import Nutrition, nutrition_per_serving
from scripts.ingredient_senses import (
    DAIRY_SLUG,
    guess_allergen_ids,
    is_non_dairy_lookalike,
    is_vegetarian_version,
    mentions_animal_derived,
    mentions_meat,
    resolve_ambiguous_name,
)
from scripts.process_vifoodrec import ID_PREFIX as VIFOODREC_ID_PREFIX
from scripts.step_cleaning import clean_steps

MIN_MATCHED_RATIO = 0.9
# Food.com RAW không có số khẩu phần lẫn định lượng → khẩu phần mặc định, không tính được dinh dưỡng.
FOODCOM_DEFAULT_SERVINGS = 4
FOODCOM_RECIPE_URL = "https://www.food.com/recipe/{id}"
# Ngoài khoảng này gần như chắc chắn do định lượng nguồn sai/không đại diện (1 lít dầu chiên ngập, mẻ bánh tét 3kg nếp).
MIN_KCAL_PER_SERVING = 20
MAX_KCAL_PER_SERVING = 2000

REJECT_LOW_MATCH = f"match < {MIN_MATCHED_RATIO:.0%} nguyên liệu chính"
REJECT_KCAL_OUTLIER = f"kcal/khẩu phần ngoài {MIN_KCAL_PER_SERVING}–{MAX_KCAL_PER_SERVING}"
REJECT_DUPLICATE_TITLE = "trùng tên công thức"

# Gia vị cơ bản (so trên bản bỏ dấu để bắt cả "hat nêm"): tên chỉ gồm các từ dưới đây và có ít nhất 1 từ "lõi",
# hoặc bắt đầu bằng 1 tiền tố. Không tính vào % match.
PANTRY_BASIC_CORE_WORDS = {"nuoc", "muoi", "tieu", "water", "salt", "pepper"}
PANTRY_BASIC_WORDS = PANTRY_BASIC_CORE_WORDS | {
    "loc", "soi", "am", "lanh", "xay", "den", "hot", "black", "white", "ground", "kosher", "sea", "table",
    "cold", "warm", "boiling", "ice", "and", "to", "taste", "freshly", "coarse",
}
ANIMAL_BASED_SEASONING_PREFIX = "hat nem"  # thường nấu từ xương heo/gà
PANTRY_BASIC_PREFIXES = (ANIMAL_BASED_SEASONING_PREFIX, "bot ngot", "bot canh", "msg")


@dataclass(frozen=True)
class DietFlags:
    is_vegetarian: bool
    is_vegan: bool


@dataclass
class Catalog:
    """Dữ liệu danh mục cần để chuẩn hoá 1 công thức."""

    normalizer: IngredientNormalizer
    diet_flags: dict[int, DietFlags]
    facts: dict[int, Nutrition]
    allergens_by_ingredient: dict[int, set[int]]
    allergen_id_by_slug: dict[str, int]


@dataclass
class PreparedRecipe:
    """1 công thức đã map xong, sẵn sàng insert."""

    title: str
    description: str
    servings: int
    prep_minutes: int
    diet_type: str
    is_verified: bool
    source_url: str | None
    grams_by_ingredient: dict[int, float | None]
    steps: list[str]
    allergen_ids: set[int]
    nutrition: Nutrition | None
    raw_ingredient_names: list[str]  # tên gốc không map được, giữ nguyên văn


@dataclass
class IngredientMapping:
    """Kết quả map các tên nguyên liệu của 1 công thức."""

    grams_by_ingredient: dict[int, float | None]
    unmatched: list[str]
    fuzzy_matched: list[str]


def _basic_key(name: str) -> str:
    return strip_diacritics(clean_ingredient_name(name))


def is_pantry_basic(name: str) -> bool:
    """Nước, muối, tiêu, hạt nêm, bột ngọt, bột canh (kể cả "salt & freshly ground black pepper")."""
    key = _basic_key(name)
    words = set(key.split())
    return key.startswith(PANTRY_BASIC_PREFIXES) or (bool(words & PANTRY_BASIC_CORE_WORDS) and words <= PANTRY_BASIC_WORDS)


def is_diet_neutral_basic(name: str) -> bool:
    """Gia vị cơ bản chắc chắn thuần chay — hạt nêm thì không."""
    return is_pantry_basic(name) and not _basic_key(name).startswith(ANIMAL_BASED_SEASONING_PREFIX)


def is_contradictory_fuzzy_match(name: str, ingredient_id: int, catalog: Catalog) -> bool:
    """Khớp mờ trái nghĩa với tên gốc → coi như không map được, vd "cá cam" → Cam, "dầu hào chay" → Dầu hào."""
    flags = catalog.diet_flags[ingredient_id]
    is_dairy = catalog.allergen_id_by_slug[DAIRY_SLUG] in catalog.allergens_by_ingredient.get(ingredient_id, set())
    return (
        is_pantry_basic(name)  # gia vị cơ bản chỉ nhận khớp chính xác ("nước ấm" ≠ Nước mắm)
        or (mentions_meat(name) and flags.is_vegetarian)
        or (is_vegetarian_version(name) and not flags.is_vegetarian)
        or (is_non_dairy_lookalike(name) and is_dairy)
    )


def classify_diet(
    ingredient_ids: set[int], diet_flags: dict[int, DietFlags], unmatched: list[str], fuzzy_matched: list[str],
) -> str:
    """is_animal (không chay) → omnivore; is_animal_derived (chay, không thuần chay) → vegetarian; còn lại vegan."""
    # Tên không map được có thể là thịt ("bacon"); tên khớp mờ có thể bị map nhầm → không tin nhãn chay.
    if (
        any(not is_diet_neutral_basic(name) and not is_non_dairy_lookalike(name) for name in unmatched)
        or any(mentions_meat(name) for name in fuzzy_matched)
        or any(not diet_flags[ingredient_id].is_vegetarian for ingredient_id in ingredient_ids)
    ):
        return "omnivore"
    if any(mentions_animal_derived(name) for name in fuzzy_matched) or any(
        not diet_flags[ingredient_id].is_vegan for ingredient_id in ingredient_ids
    ):
        return "vegetarian"
    return "vegan"


def map_ingredients(
    names: list[str], dish_title: str, grams_by_name: dict[str, float], catalog: Catalog,
) -> IngredientMapping:
    """Tên → {ingredient_id: gram hoặc None}, kèm tên không map được và tên chỉ khớp mờ."""
    mapping = IngredientMapping({}, [], [])
    resolved = [resolve_ambiguous_name(name, dish_title) for name in names]
    for name, match in zip(names, catalog.normalizer.normalize(resolved)):
        if match.status is not MatchStatus.ACCEPTED or (
            not match.is_exact and is_contradictory_fuzzy_match(name, match.ingredient_id, catalog)
        ):
            mapping.unmatched.append(name)
            continue
        if not match.is_exact:
            mapping.fuzzy_matched.append(name)
        grams = grams_by_name.get(name)
        previous = mapping.grams_by_ingredient.get(match.ingredient_id)
        # 2 tên cùng 1 nguyên liệu ("tỏi" + "tỏi băm") → cộng gram; thiếu gram ở 1 bên thì giữ bên có.
        mapping.grams_by_ingredient[match.ingredient_id] = (previous or 0) + grams if grams else previous
    return mapping


def matched_ratio(names: list[str], unmatched: list[str]) -> float:
    """Tỉ lệ nguyên liệu chính map được (bỏ gia vị cơ bản khỏi cả tử lẫn mẫu)."""
    main_count = sum(not is_pantry_basic(name) for name in names)
    if main_count == 0:
        return 0.0
    return 1 - sum(not is_pantry_basic(name) for name in unmatched) / main_count


def prepare_recipe(
    row: dict[str, str], catalog: Catalog, extras: dict[str, tuple[int, dict[str, float]]],
) -> PreparedRecipe | str:
    """1 dòng CSV → PreparedRecipe, hoặc lý do loại."""
    names: list[str] = ast.literal_eval(row["ingredients"])
    title = row["name"].strip()
    is_vifoodrec = row["id"].startswith(VIFOODREC_ID_PREFIX)
    servings, grams_by_name = extras.get(row["id"], (FOODCOM_DEFAULT_SERVINGS, {}))
    mapping = map_ingredients(names, title, grams_by_name, catalog)
    if matched_ratio(names, mapping.unmatched) < MIN_MATCHED_RATIO:
        return REJECT_LOW_MATCH
    known_grams = {ingredient_id: grams for ingredient_id, grams in mapping.grams_by_ingredient.items() if grams}
    nutrition = nutrition_per_serving(known_grams, catalog.facts, servings) if known_grams else None
    if nutrition is not None and not MIN_KCAL_PER_SERVING <= nutrition.kcal <= MAX_KCAL_PER_SERVING:
        return REJECT_KCAL_OUTLIER
    ingredient_ids = set(mapping.grams_by_ingredient)
    return PreparedRecipe(
        title=title,
        description=row["description"].strip(),
        servings=servings,
        prep_minutes=int(row["minutes"]),
        diet_type=classify_diet(ingredient_ids, catalog.diet_flags, mapping.unmatched, mapping.fuzzy_matched),
        is_verified=is_vifoodrec,
        source_url=None if is_vifoodrec else FOODCOM_RECIPE_URL.format(id=row["id"]),
        grams_by_ingredient=mapping.grams_by_ingredient,
        steps=clean_steps(ast.literal_eval(row["steps"])),
        allergen_ids=set().union(
            *(catalog.allergens_by_ingredient.get(ingredient_id, set()) for ingredient_id in ingredient_ids),
            guess_allergen_ids(mapping.unmatched + mapping.fuzzy_matched, catalog.allergen_id_by_slug),
        ),
        nutrition=nutrition,
        raw_ingredient_names=mapping.unmatched,
    )


def prepare_all(
    rows: list[dict[str, str]], catalog: Catalog, extras: dict[str, tuple[int, dict[str, float]]],
    existing_titles: set[str],
) -> tuple[list[PreparedRecipe], Counter]:
    """Chuẩn hoá mọi dòng; trả công thức giữ lại + đếm lý do loại."""
    kept: list[PreparedRecipe] = []
    rejections: Counter = Counter()
    seen_titles = set(existing_titles)
    for row in rows:
        result = prepare_recipe(row, catalog, extras)
        if isinstance(result, str):
            rejections[result] += 1
        elif result.title.lower() in seen_titles:
            rejections[REJECT_DUPLICATE_TITLE] += 1
        else:
            seen_titles.add(result.title.lower())
            kept.append(result)
    return kept, rejections
