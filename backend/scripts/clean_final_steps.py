"""Dọn bước cuối của các công thức đã có trong recipe_steps (xem scripts/step_cleaning.py).

Chạy từ thư mục backend: python -m scripts.clean_final_steps [--dry-run]  (chạy lại an toàn: bước đã sạch giữ nguyên)
"""

import argparse
import logging
import random

from supabase import Client

from scripts.seed_recipes import fetch_all_rows
from scripts.step_cleaning import clean_final_step
from scripts.supabase_admin import create_admin_client

logger = logging.getLogger(__name__)

SAMPLES_TO_PRINT = 8
PROGRESS_LOG_EVERY = 200


def final_steps(client: Client) -> list[dict]:
    """Bước cuối (step_no lớn nhất) của mỗi công thức có từ 2 bước trở lên."""
    steps_by_recipe: dict[int, list[dict]] = {}
    for row in fetch_all_rows(client, "recipe_steps", "recipe_id,step_no,instruction"):
        steps_by_recipe.setdefault(row["recipe_id"], []).append(row)
    return [max(steps, key=lambda step: step["step_no"]) for steps in steps_by_recipe.values() if len(steps) >= 2]


def apply_change(client: Client, step: dict, cleaned: str | None) -> None:
    """Xoá bước (cleaned None) hoặc thay nội dung đã cắt câu quảng cáo."""
    query = client.table("recipe_steps")
    query = query.delete() if cleaned is None else query.update({"instruction": cleaned})
    query.eq("recipe_id", step["recipe_id"]).eq("step_no", step["step_no"]).execute()


def main() -> None:
    """Tính thay đổi cho bước cuối mọi công thức, in mẫu + thống kê, ghi trừ khi --dry-run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ in thống kê + mẫu, không ghi DB")
    dry_run = parser.parse_args().dry_run

    client = create_admin_client()
    steps = final_steps(client)
    changes = [(step, clean_final_step(step["instruction"])) for step in steps]
    changes = [(step, cleaned) for step, cleaned in changes if cleaned != step["instruction"]]
    removed = [change for change in changes if change[1] is None]
    trimmed = [change for change in changes if change[1] is not None]

    for label, group in (("XOÁ", removed), ("CẮT", trimmed)):
        for step, cleaned in random.sample(group, min(SAMPLES_TO_PRINT, len(group))):
            print(f"[{label}] recipe {step['recipe_id']} bước {step['step_no']}: {step['instruction']}")
            if cleaned is not None:
                print(f"   → {cleaned}")
    if not dry_run:
        for count, (step, cleaned) in enumerate(changes, start=1):
            apply_change(client, step, cleaned)
            if count % PROGRESS_LOG_EVERY == 0:
                logger.info("Đã xử lý %d/%d", count, len(changes))
    print(f"\nBước cuối xét: {len(steps)} — xoá cả bước: {len(removed)} — cắt câu quảng cáo: {len(trimmed)} "
          f"— giữ nguyên: {len(steps) - len(changes)}{' (dry-run, chưa ghi)' if dry_run else ''}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logger.setLevel(logging.INFO)
    main()
