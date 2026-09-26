"""Seed bảng food_safety theo nhiệt độ lõi tối thiểu của USDA FSIS.

Chạy từ thư mục backend: python -m scripts.seed_food_safety  (chạy lại an toàn — upsert theo category)
"""

import logging

from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

# Nhiệt độ + rest: USDA FSIS "Safe Minimum Internal Temperature Chart".
# Thời gian giữ ở nhiệt độ (min_duration_sec): FDA Food Code 2022 — ¶3-401.11 (Annex 7, Chart 4-A) và ¶3-403.11.
#   ở 74°C (gia cầm) và ≥70°C (thịt xay, trứng không phục vụ ngay): < 1 giây, tức thời → 0
#   ở 63°C (cá, heo, thịt nguyên miếng): giữ 15 giây;  hâm nóng đồ ăn thừa 74°C: giữ 15 giây
# FSIS: thịt nguyên miếng / giăm bông sống để nghỉ 3 phút sau khi tắt bếp — không phải thời gian nấu
INSTANT_KILL_SEC = 0
FOOD_CODE_HOLD_SEC = 15
REST_3_MIN_SEC = 180
FOOD_SAFETY_THRESHOLDS = [
    {"category": "whole_cut", "min_temp_c": 63, "min_duration_sec": FOOD_CODE_HOLD_SEC, "rest_sec": REST_3_MIN_SEC,
     "note": "Bò/heo/cừu/bê nguyên miếng; để nghỉ 3 phút sau khi nấu"},
    {"category": "ground_meat", "min_temp_c": 71, "min_duration_sec": INSTANT_KILL_SEC, "rest_sec": 0,
     "note": "Thịt bò/heo/cừu xay"},
    {"category": "poultry", "min_temp_c": 74, "min_duration_sec": INSTANT_KILL_SEC, "rest_sec": 0,
     "note": "Gà, vịt, gà tây — cả nguyên con lẫn xay"},
    {"category": "egg_dish", "min_temp_c": 71, "min_duration_sec": INSTANT_KILL_SEC, "rest_sec": 0,
     "note": "Món có trứng"},
    {"category": "fish_shellfish", "min_temp_c": 63, "min_duration_sec": FOOD_CODE_HOLD_SEC, "rest_sec": 0,
     "note": "Cá và hải sản có vỏ"},
    {"category": "ham_raw", "min_temp_c": 63, "min_duration_sec": FOOD_CODE_HOLD_SEC, "rest_sec": REST_3_MIN_SEC,
     "note": "Giăm bông sống/tươi; để nghỉ 3 phút sau khi nấu"},
    {"category": "leftovers_casserole", "min_temp_c": 74, "min_duration_sec": FOOD_CODE_HOLD_SEC, "rest_sec": 0,
     "note": "Hâm nóng đồ ăn thừa, món casserole"},
]


def seed_food_safety() -> None:
    """Upsert toàn bộ ngưỡng an toàn vào food_safety."""
    client = create_admin_client()
    client.table("food_safety").upsert(FOOD_SAFETY_THRESHOLDS, on_conflict="category").execute()
    logger.info("Đã upsert %d dòng food_safety", len(FOOD_SAFETY_THRESHOLDS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_food_safety()
