"""Chuẩn hoá dataset ViFoodRec (github.com/QuocAn55/DS300) về cùng format với data/foodcom_filtered.csv.

Chạy từ thư mục backend, SAU khi clone repo vào data/vifoodrec: python -m scripts.process_vifoodrec
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

from app.services.ingredient_normalizer import clean_ingredient_name

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FOODS_CSV = DATA_DIR / "vifoodrec" / "Data" / "Clean Dataset" / "foods.csv"
RATINGS_CSV = DATA_DIR / "vifoodrec" / "Data" / "Clean Dataset" / "ratings.csv"
OUTPUT_CSV = DATA_DIR / "vifoodrec_processed.csv"

# Cột giống hệt foodcom_filtered.csv để 2 nguồn gộp chung được.
FOODCOM_COLUMNS = (
    "name", "id", "minutes", "contributor_id", "submitted", "tags", "nutrition", "n_steps", "steps",
    "description", "ingredients", "n_ingredients", "avg_rating", "review_count",
)
# Tiền tố id để không đụng id số của Food.com khi gộp.
ID_PREFIX = "vifoodrec-"
# Món 1 bước thường là cách làm bị cắt cụt ở nguồn. Không lọc rating (thang khác Food.com), món ngọt/đồ uống.
MIN_STEPS = 2

# Bản "Clean" bị lỗi thay "m" thành "muỗng" ("600 muỗngl", "2 muỗngặt", "1 muỗnguỗng canh").
# "muỗng" thật luôn có khoảng trắng/dấu câu theo sau, nên "muỗng" dính liền chữ cái = bị lỗi → trả lại "m".
_BROKEN_M = re.compile(r"muỗng(?=[^\W\d_])")
# Các bước trong cooking_method nối bằng "., "; không có dấu này thì tách theo câu.
_STEP_SEPARATOR = re.compile(r"(?<=\.),\s+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[^\W\d_])")
_DIGIT = re.compile(r"\d")
# Số lượng bắt đầu từ chữ số đầu tiên (kể cả phân số unicode): "Trứng gà 2 Cái" → "Trứng gà ".
_QUANTITY_TAIL = re.compile(r"[\d½¼¾⅓⅔].*")
_DIGIT_RUN = re.compile(r"\d+")
_MASS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|gram|gr|g|ml|lít|l)\b", re.IGNORECASE)
# ml/lít quy ra gram theo tỉ trọng nước — đủ gần cho nước dùng, sữa, nước mắm.
GRAMS_PER_UNIT = {"kg": 1000, "gram": 1, "gr": 1, "g": 1, "ml": 1, "lít": 1000, "l": 1000}
DEFAULT_SERVINGS = 4
# Nguồn có lỗi gõ kiểu "Vải thiều 500kg" → coi như không có định lượng.
MAX_PLAUSIBLE_GRAMS = 5000


def fix_broken_m(text: str) -> str:
    """Sửa lỗi "muỗng" chèn nhầm thay cho chữ "m" trong dataset gốc."""
    return _BROKEN_M.sub("m", text)


def split_cooking_steps(cooking_method: str) -> list[str]:
    """Tách đoạn cooking_method thành list các bước (bỏ bước rỗng)."""
    parts = _STEP_SEPARATOR.split(cooking_method)
    if len(parts) == 1:
        parts = _SENTENCE_BOUNDARY.split(cooking_method)
    return [part.strip() for part in parts if part.strip()]


def _parse_ingredient_item(item: str) -> tuple[str, float | None]:
    """1 mục nguyên liệu → (tên đã làm sạch, số gram nếu ghi bằng g/kg/ml/l)."""
    label, _, detail = item.partition(":")
    # "Tên: 400g" → lấy tên; "Gia vị: tiêu" (sau dấu ":" không có số) → lấy phần sau.
    name = detail if detail and not _DIGIT.search(detail) else label
    # Số lượng đứng sau tên ("Trứng gà 2 Cái") thì cắt đuôi; đứng trước ("400gr cua đồng") để clean xử lý.
    cleaned = clean_ingredient_name(_QUANTITY_TAIL.sub("", name).strip() or name)
    mass = _MASS.search(item)
    grams = float(mass.group(1).replace(",", ".")) * GRAMS_PER_UNIT[mass.group(2).lower()] if mass else None
    return cleaned, grams if grams and grams <= MAX_PLAUSIBLE_GRAMS else None


def extract_ingredient_names(ingredients: str) -> list[str]:
    """ "Cá bớp: 400g, Gia vị: tiêu, đường" → ["cá bớp", "tiêu", "đường"] — chỉ tên, như cột ingredients của Food.com."""
    names: list[str] = []
    for item in ingredients.split(","):
        name, _ = _parse_ingredient_item(item)
        if name and name not in names:
            names.append(name)
    return names


def extract_ingredient_grams(ingredients: str) -> dict[str, float]:
    """Tên đã làm sạch → số gram, chỉ cho mục ghi bằng đơn vị khối lượng/thể tích."""
    grams_by_name: dict[str, float] = {}
    for item in ingredients.split(","):
        name, grams = _parse_ingredient_item(item)
        if name and grams:
            grams_by_name[name] = grams_by_name.get(name, 0) + grams
    return grams_by_name


def read_servings_and_grams() -> dict[str, tuple[int, dict[str, float]]]:
    """id (có ID_PREFIX) → (số khẩu phần, gram theo tên nguyên liệu) — phần mà file processed không giữ."""
    extras: dict[str, tuple[int, dict[str, float]]] = {}
    with FOODS_CSV.open(encoding="utf-8", newline="") as file:
        for food in csv.DictReader(file):
            servings = _DIGIT_RUN.search(food["serving_size"])
            extras[ID_PREFIX + food["food_id"]] = (
                int(servings.group()) if servings else DEFAULT_SERVINGS,
                extract_ingredient_grams(fix_broken_m(food["ingredients"])),
            )
    return extras


def collect_rating_stats(ratings_csv: Path) -> dict[str, tuple[float, int]]:
    """food_id → (điểm trung bình, số lượt đánh giá)."""
    ratings: dict[str, list[float]] = defaultdict(list)
    with ratings_csv.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            ratings[row["foodId"]].append(float(row["rating"]))
    return {food_id: (sum(values) / len(values), len(values)) for food_id, values in ratings.items()}


def to_foodcom_row(food: dict[str, str], rating_stats: tuple[float, int] | None) -> dict[str, object] | None:
    """Chuyển 1 dòng foods.csv sang format Food.com; None nếu dưới MIN_STEPS bước hoặc không có nguyên liệu."""
    steps = split_cooking_steps(fix_broken_m(food["cooking_method"]))
    ingredients = extract_ingredient_names(fix_broken_m(food["ingredients"]))
    if len(steps) < MIN_STEPS or not ingredients:
        return None
    avg_rating, review_count = rating_stats or (0.0, 0)
    tags = [food["dish_type"], *(tag.strip() for tag in food["dish_tags"].split(",") if tag.strip())]
    return {
        "name": food["dish_name"].strip(),
        "id": ID_PREFIX + food["food_id"],
        "minutes": food["cooking_time"],
        "contributor_id": "",
        "submitted": "",
        "tags": repr(tags),
        # Để trống: số của ViFoodRec là gram/khẩu phần, Food.com là %DV — không cùng đơn vị.
        # Dinh dưỡng thật luôn tính từ nutrition_facts.
        "nutrition": repr([]),
        "n_steps": len(steps),
        "steps": repr(steps),
        "description": fix_broken_m(food["description"]).strip(),
        "ingredients": repr(ingredients),
        "n_ingredients": len(ingredients),
        "avg_rating": round(avg_rating, 2),
        "review_count": review_count,
    }


def main() -> None:
    """Đọc foods + ratings, chuẩn hoá, ghi vifoodrec_processed.csv và in số món còn lại."""
    rating_stats = collect_rating_stats(RATINGS_CSV)
    kept = 0
    with FOODS_CSV.open(encoding="utf-8", newline="") as source, OUTPUT_CSV.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FOODCOM_COLUMNS)
        writer.writeheader()
        for food in csv.DictReader(source):
            row = to_foodcom_row(food, rating_stats.get(food["food_id"]))
            if row is None:
                continue
            writer.writerow(row)
            kept += 1
    print(f"Còn lại {kept} món → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
