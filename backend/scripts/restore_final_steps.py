"""Khôi phục bước cuối bị clean_final_steps xoá nhầm, theo rule hiện tại của step_cleaning (lấy lại từ CSV gốc).

So recipe_steps trong DB với danh sách bước pipeline seed sinh ra từ CSV: món nào DB thiếu đúng 1 bước cuối
mà rule hiện tại giữ lại → chèn bước đó vào step_no cuối.
Chạy từ thư mục backend: python -m scripts.restore_final_steps [--dry-run]  (chạy lại an toàn)
"""

import argparse

from scripts.backfill_raw_ingredient_names import rebuild_prepared_by_recipe_id
from scripts.seed_recipes import fetch_all_rows
from scripts.step_cleaning import clean_final_step
from scripts.supabase_admin import create_admin_client


def main() -> None:
    """Tìm bước cuối cần khôi phục, in ra, ghi trừ khi --dry-run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ in, không ghi DB")
    dry_run = parser.parse_args().dry_run

    client = create_admin_client()
    db_steps: dict[int, list[str]] = {}
    for row in sorted(fetch_all_rows(client, "recipe_steps", "recipe_id,step_no,instruction"),
                      key=lambda row: (row["recipe_id"], row["step_no"])):
        db_steps.setdefault(row["recipe_id"], []).append(row["instruction"])

    to_restore = []
    for recipe_id, prepared in rebuild_prepared_by_recipe_id(client).items():
        current = db_steps.get(recipe_id, [])
        # Chỉ khôi phục bước mà rule vẫn giữ nếu nó là bước cuối — bước rác "mới thành cuối" đã xoá có chủ đích
        # (vd "goes well with any thai dish") nằm giữa trong CSV nên pipeline còn giữ, không được chèn lại.
        if (
            len(prepared.steps) == len(current) + 1
            and prepared.steps[:-2] == current[:-1]
            and clean_final_step(prepared.steps[-1]) is not None
        ):
            to_restore.append((recipe_id, len(prepared.steps), prepared.steps[-1]))

    for recipe_id, step_no, instruction in to_restore:
        print(f"  recipe {recipe_id} bước {step_no}: {instruction}")
    if not dry_run and to_restore:
        client.table("recipe_steps").insert([
            {"recipe_id": recipe_id, "step_no": step_no, "instruction": instruction}
            for recipe_id, step_no, instruction in to_restore
        ]).execute()
    print(f"Khôi phục: {len(to_restore)} bước{' (dry-run, chưa ghi)' if dry_run else ''}")


if __name__ == "__main__":
    main()
