"""Seed bảng ingredients + nutrition_facts.

Nguồn 1: data/ingredients_usda.csv — danh mục nguyên liệu, dinh dưỡng lấy từ USDA FoodData Central.
Nguồn 2: data/ingredients_vn_manual.csv (nếu có) — món Việt USDA không có, dinh dưỡng điền tay.

Chạy từ thư mục backend, SAU seed_food_safety: python -m scripts.seed_ingredients
Chạy lại an toàn: nguyên liệu trùng name_vi (không phân biệt hoa thường) được bỏ qua.
"""

import csv
import logging
from pathlib import Path

import httpx
from supabase import Client

from app.core.config import require_env
from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
USDA_INGREDIENTS_CSV = DATA_DIR / "ingredients_usda.csv"
MANUAL_INGREDIENTS_CSV = DATA_DIR / "ingredients_vn_manual.csv"

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_DATA_TYPES = ["Foundation", "SR Legacy"]
USDA_CANDIDATES_PER_QUERY = 5
USDA_TIMEOUT_SECONDS = 20.0

# Mã nutrientNumber của USDA; Foundation hay thiếu 208 nên dự phòng bằng năng lượng Atwater (958, 957)
ENERGY_KCAL_NUMBERS = ("208", "958", "957")
PROTEIN_NUMBER = "203"
FAT_NUMBER = "204"
CARB_NUMBER = "205"

MANUAL_SOURCE = "manual"
TRUTHY_FLAG_VALUES = {"1", "true"}
ALIAS_SEPARATOR = "|"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Đọc CSV UTF-8 thành list dict theo header."""
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def parse_flag(value: str) -> bool:
    """Đọc cờ boolean trong CSV: chấp nhận 1/0 và TRUE/FALSE."""
    return value.strip().lower() in TRUTHY_FLAG_VALUES


def to_sentence_case(text: str) -> str:
    """Viết hoa chữ cái đầu, phần còn lại viết thường ("đậu Hà Lan" → "Đậu hà lan")."""
    text = text.strip()
    return text[:1].upper() + text[1:].lower()


def parse_aliases(value: str) -> list[str]:
    """Tách cột aliases dạng "Tên 1|Tên 2" thành list, đã chuẩn hoá casing."""
    return [to_sentence_case(alias) for alias in value.split(ALIAS_SEPARATOR) if alias.strip()]


def known_names(record: dict) -> set[str]:
    """Tên chính + aliases (lowercase) của 1 nguyên liệu — dùng để phát hiện trùng."""
    return {name.lower() for name in [record["name_vi"], *record["aliases"]]}


def build_ingredient_record(row: dict[str, str], safety_ids: dict[str, int]) -> dict:
    """Chuyển 1 dòng CSV thành record bảng ingredients (suy ra cờ chay/thuần chay từ nguồn gốc động vật)."""
    is_animal = parse_flag(row["is_animal"])
    is_animal_derived = parse_flag(row["is_animal_derived"])
    safety_category = row["safety_category"].strip()
    if safety_category and safety_category not in safety_ids:
        raise ValueError(f"{row['name_vi']}: safety_category '{safety_category}' chưa có trong food_safety")
    return {
        "name_vi": to_sentence_case(row["name_vi"]),
        "name_en": to_sentence_case(row["name_en"]) or None,
        "aliases": parse_aliases(row.get("aliases") or ""),
        "category": row["category"].strip(),
        "is_vegetarian": not is_animal,
        "is_vegan": not is_animal and not is_animal_derived,
        "food_safety_id": safety_ids.get(safety_category),
    }


def extract_usda_macros(food: dict) -> dict | None:
    """Lấy kcal/đạm/tinh bột/béo trên 100g từ 1 kết quả USDA; None nếu thiếu chỉ số nào."""
    values = {item.get("nutrientNumber"): item for item in food.get("foodNutrients", [])}
    energy = next(
        (values[number] for number in ENERGY_KCAL_NUMBERS
         if number in values and values[number].get("unitName") == "KCAL"),
        None,
    )
    macros = [values.get(number) for number in (PROTEIN_NUMBER, CARB_NUMBER, FAT_NUMBER)]
    if energy is None or None in macros:
        return None
    protein, carb, fat = (round(item["value"], 2) for item in macros)
    return {
        "kcal_100g": round(energy["value"], 2),
        "protein_g": protein,
        "carb_g": carb,
        "fat_g": fat,
        "source": f"USDA FDC {food['fdcId']} ({food['dataType']}): {food['description']}",
    }


def search_usda_macros(http: httpx.Client, api_key: str, query: str) -> dict | None:
    """Tìm trên USDA (chỉ Foundation/SR Legacy), trả dinh dưỡng của kết quả đầu tiên đủ chỉ số."""
    response = http.post(
        USDA_SEARCH_URL,
        params={"api_key": api_key},
        json={"query": query, "dataType": USDA_DATA_TYPES, "pageSize": USDA_CANDIDATES_PER_QUERY},
    )
    response.raise_for_status()
    for food in response.json().get("foods", []):
        macros = extract_usda_macros(food)
        if macros:
            return macros
    return None


def read_manual_macros(row: dict[str, str]) -> dict:
    """Dinh dưỡng điền tay trong CSV thủ công."""
    return {
        "kcal_100g": float(row["kcal_100g"]),
        "protein_g": float(row["protein_g"]),
        "carb_g": float(row["carbs_g"]),
        "fat_g": float(row["fat_g"]),
        "source": MANUAL_SOURCE,
    }


def collect_usda_ingredients(safety_ids: dict[str, int], existing: set[str]) -> list[tuple[dict, dict]]:
    """Ghép danh mục USDA CSV với dinh dưỡng tra từ API; bỏ qua dòng đã có hoặc không tìm thấy."""
    api_key = require_env("USDA_API_KEY")
    pairs = []
    with httpx.Client(timeout=USDA_TIMEOUT_SECONDS) as http:
        for row in read_csv_rows(USDA_INGREDIENTS_CSV):
            if to_sentence_case(row["name_vi"]).lower() in existing:
                continue
            macros = search_usda_macros(http, api_key, row["usda_query"])
            if macros is None:
                logger.warning("USDA không có kết quả đủ chỉ số cho '%s' — bỏ qua", row["usda_query"])
                continue
            pairs.append((build_ingredient_record(row, safety_ids), macros))
    return pairs


def collect_manual_ingredients(safety_ids: dict[str, int], existing: set[str]) -> list[tuple[dict, dict]]:
    """Đọc CSV thủ công nếu tồn tại; bỏ qua dòng trùng tên chính hoặc alias đã có."""
    if not MANUAL_INGREDIENTS_CSV.exists():
        return []
    pairs = []
    for row in read_csv_rows(MANUAL_INGREDIENTS_CSV):
        record = build_ingredient_record(row, safety_ids)
        if known_names(record).isdisjoint(existing):
            pairs.append((record, read_manual_macros(row)))
    return pairs


def insert_ingredients(client: Client, pairs: list[tuple[dict, dict]]) -> None:
    """Insert ingredients rồi nutrition_facts gắn theo id vừa sinh."""
    # ponytail: 2 request không cùng transaction — nếu bước 2 lỗi, xoá các ingredient thiếu nutrition rồi chạy lại
    inserted = client.table("ingredients").insert([record for record, _ in pairs]).execute().data
    id_by_name = {row["name_vi"]: row["id"] for row in inserted}
    nutrition_rows = [{"ingredient_id": id_by_name[record["name_vi"]], **macros} for record, macros in pairs]
    client.table("nutrition_facts").insert(nutrition_rows).execute()


def sync_aliases(client: Client, existing_rows: list[dict]) -> int:
    """Gộp aliases trong USDA CSV vào nguyên liệu đã có (bước insert bỏ qua dòng trùng tên nên không cập nhật aliases)."""
    by_name = {row["name_vi"].lower(): row for row in existing_rows}
    updated = 0
    for csv_row in read_csv_rows(USDA_INGREDIENTS_CSV):
        db_row = by_name.get(to_sentence_case(csv_row["name_vi"]).lower())
        if db_row is None:
            continue
        merged = list(dict.fromkeys([*db_row["aliases"], *parse_aliases(csv_row.get("aliases") or "")]))
        if merged != db_row["aliases"]:
            client.table("ingredients").update({"aliases": merged}).eq("id", db_row["id"]).execute()
            updated += 1
    return updated


def seed_ingredients() -> None:
    """Seed toàn bộ nguyên liệu từ USDA + CSV thủ công."""
    client = create_admin_client()
    safety_rows = client.table("food_safety").select("id, category").execute().data
    safety_ids = {row["category"]: row["id"] for row in safety_rows}
    existing_rows = client.table("ingredients").select("id, name_vi, aliases").execute().data
    logger.info("Đã cập nhật aliases cho %d nguyên liệu có sẵn", sync_aliases(client, existing_rows))
    existing = set().union(*(known_names(row) for row in existing_rows))

    usda_pairs = collect_usda_ingredients(safety_ids, existing)
    # Tên/alias đã lấy từ USDA thì bỏ bản thủ công trùng, tránh vi phạm unique index trong cùng 1 lần insert
    names_from_usda = set().union(*(known_names(record) for record, _ in usda_pairs))
    pairs = usda_pairs + collect_manual_ingredients(safety_ids, existing | names_from_usda)
    if not pairs:
        logger.info("Không có nguyên liệu mới để insert")
        return
    insert_ingredients(client, pairs)
    logger.info("Đã insert %d nguyên liệu (DB đã có %d)", len(pairs), len(existing_rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_ingredients()
