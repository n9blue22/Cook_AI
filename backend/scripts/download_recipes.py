"""Tải dataset Food.com từ Kaggle, lọc công thức chất lượng cao, lưu data/foodcom_filtered.csv.

Chạy từ thư mục backend: python -m scripts.download_recipes
Token Kaggle: biến KAGGLE_API_TOKEN, ~/.kaggle/access_token, hoặc .kaggle/access_token ở gốc repo.
"""

import ast
import csv
import logging
import os
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw" / "foodcom"
OUTPUT_CSV = DATA_DIR / "foodcom_filtered.csv"
# Cột steps/description rất dài; 2^31-1 vì Windows không nhận sys.maxsize.
CSV_FIELD_SIZE_LIMIT = 2**31 - 1

KAGGLE_DATASET = "shuyangli94/food-com-recipes-and-user-interactions"
RECIPES_FILE = "RAW_recipes.csv"
INTERACTIONS_FILE = "RAW_interactions.csv"

MIN_AVG_RATING = 4.3
MIN_REVIEWS = 10
MIN_MINUTES, MAX_MINUTES = 10, 90
MIN_STEPS, MAX_STEPS = 3, 15
MIN_INGREDIENTS, MAX_INGREDIENTS = 4, 14
MIN_STEP_CHARS = 15
EXCLUDED_TAG_KEYWORDS = ("dessert", "beverage", "cocktail")
# Food.com: rating 0 = review không chấm sao → tính vào số review, không tính vào điểm trung bình.
UNRATED = 0


@dataclass
class RecipeStats:
    """Thống kê review của 1 công thức."""

    review_count: int = 0
    rating_sum: int = 0
    rated_count: int = 0

    @property
    def avg_rating(self) -> float:
        return self.rating_sum / self.rated_count if self.rated_count else 0.0


def download_raw_files() -> None:
    """Tải RAW_recipes + RAW_interactions (bỏ qua file đã có)."""
    repo_token = REPO_ROOT / ".kaggle" / "access_token"
    if repo_token.exists():
        os.environ.setdefault("KAGGLE_API_TOKEN", str(repo_token))
    from kaggle import api  # import sau khi set token: kaggle xác thực ngay lúc import

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for file_name in (RECIPES_FILE, INTERACTIONS_FILE):
        if (RAW_DIR / file_name).exists():
            continue
        logger.info("Đang tải %s ...", file_name)
        api.dataset_download_file(KAGGLE_DATASET, file_name, path=str(RAW_DIR), quiet=False)
        _unzip_if_needed(RAW_DIR / file_name)


def _unzip_if_needed(target: Path) -> None:
    """Kaggle có thể trả file dạng <tên>.zip — giải nén ra đúng tên gốc."""
    zipped = target.with_name(target.name + ".zip")
    if not zipped.exists():
        return
    with zipfile.ZipFile(zipped) as archive:
        archive.extractall(RAW_DIR)
    zipped.unlink()


def collect_review_stats(interactions_csv: Path) -> dict[str, RecipeStats]:
    """Gom số review và điểm trung bình theo recipe_id."""
    stats: dict[str, RecipeStats] = defaultdict(RecipeStats)
    with interactions_csv.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            recipe_stats = stats[row["recipe_id"]]
            recipe_stats.review_count += 1
            rating = int(row["rating"])
            if rating != UNRATED:
                recipe_stats.rating_sum += rating
                recipe_stats.rated_count += 1
    return stats


def is_good_recipe(row: dict[str, str], stats: RecipeStats | None) -> bool:
    """Áp toàn bộ tiêu chí lọc cho 1 dòng RAW_recipes."""
    if stats is None or stats.review_count < MIN_REVIEWS or stats.avg_rating < MIN_AVG_RATING:
        return False
    if not (MIN_MINUTES <= int(row["minutes"]) <= MAX_MINUTES):
        return False
    if not (MIN_INGREDIENTS <= int(row["n_ingredients"]) <= MAX_INGREDIENTS):
        return False
    steps = ast.literal_eval(row["steps"])
    if not (MIN_STEPS <= len(steps) <= MAX_STEPS) or any(len(step.strip()) <= MIN_STEP_CHARS for step in steps):
        return False
    tags = ast.literal_eval(row["tags"])
    return not any(keyword in tag for tag in tags for keyword in EXCLUDED_TAG_KEYWORDS)


def filter_recipes(recipes_csv: Path, stats_by_recipe: dict[str, RecipeStats], output_csv: Path) -> int:
    """Ghi các công thức đạt chuẩn (kèm avg_rating, review_count) ra output_csv, trả số dòng ghi được."""
    kept = 0
    with recipes_csv.open(encoding="utf-8", newline="") as source, output_csv.open("w", encoding="utf-8", newline="") as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=[*reader.fieldnames, "avg_rating", "review_count"])
        writer.writeheader()
        for row in reader:
            stats = stats_by_recipe.get(row["id"])
            if not is_good_recipe(row, stats):
                continue
            writer.writerow({**row, "avg_rating": round(stats.avg_rating, 2), "review_count": stats.review_count})
            kept += 1
    return kept


def main() -> None:
    """Tải → gom review → lọc → in số công thức còn lại."""
    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    download_raw_files()
    stats_by_recipe = collect_review_stats(RAW_DIR / INTERACTIONS_FILE)
    kept = filter_recipes(RAW_DIR / RECIPES_FILE, stats_by_recipe, OUTPUT_CSV)
    print(f"Còn lại {kept} công thức sau khi lọc → {OUTPUT_CSV}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
