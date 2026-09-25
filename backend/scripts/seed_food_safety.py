"""Seed bảng food_safety theo nhiệt độ lõi tối thiểu của USDA FSIS.

Chạy từ thư mục backend: python -m scripts.seed_food_safety  (chạy lại an toàn — upsert theo category)
"""

import logging

from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

# Nguồn: USDA FSIS "Safe Minimum Internal Temperature Chart"
FOOD_SAFETY_THRESHOLDS = [
    {"category": "whole_cut", "min_temp_c": 63, "note": "Bò/heo/cừu/bê nguyên miếng; để nghỉ 3 phút sau khi nấu"},
    {"category": "ground_meat", "min_temp_c": 71, "note": "Thịt bò/heo/cừu xay"},
    {"category": "poultry", "min_temp_c": 74, "note": "Gà, vịt, gà tây — cả nguyên con lẫn xay"},
    {"category": "egg_dish", "min_temp_c": 71, "note": "Món có trứng"},
    {"category": "fish_shellfish", "min_temp_c": 63, "note": "Cá và hải sản có vỏ"},
    {"category": "leftovers", "min_temp_c": 74, "note": "Hâm nóng đồ ăn thừa, món casserole"},
]


def seed_food_safety() -> None:
    """Upsert toàn bộ ngưỡng an toàn vào food_safety."""
    client = create_admin_client()
    client.table("food_safety").upsert(FOOD_SAFETY_THRESHOLDS, on_conflict="category").execute()
    logger.info("Đã upsert %d dòng food_safety", len(FOOD_SAFETY_THRESHOLDS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_food_safety()
