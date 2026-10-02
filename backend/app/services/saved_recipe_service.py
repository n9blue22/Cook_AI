"""Công thức đã lưu (feature-spec P0#9): lưu nguyên bản công thức user đã thấy (kể cả bản LLM đã chỉnh) vào
custom_payload để xem lại / tìm kiếm mà không phải gọi AI lần nữa."""

import json
from datetime import datetime, timezone
from typing import Any

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.services.diet_types import DietType
from app.services.recipe_results import SuggestedRecipe
from app.services.user_data_errors import InvalidReferenceError, NotFoundError, is_foreign_key_violation

# diet_type tra từ bảng recipes (khoá ngoại), không lấy từ payload client gửi lên — dùng cho bộ lọc "Chay".
SAVED_COLUMNS = "id,recipe_id,saved_at,custom_payload,recipes(diet_type)"
MAX_PAYLOAD_CHARS = 60_000  # 1 công thức thật ~5–10 KB; chặn payload phình to ghi vào DB
MAX_QUERY_LENGTH = 100
LIKE_SPECIAL_CHARS = ("\\", "%", "_")


class SaveRecipeIn(BaseModel):
    """POST /saved: công thức đúng như /recipes/suggest đã trả."""

    recipe: SuggestedRecipe


class SavedRecipe(BaseModel):
    """1 công thức đã lưu trả client; id là id dòng đã lưu (dùng cho DELETE /saved/{id})."""

    id: int
    recipe_id: int
    saved_at: datetime
    diet_type: DietType | None  # None khi công thức không còn đọc được (chưa kiểm duyệt)
    recipe: SuggestedRecipe


class PayloadTooLargeError(Exception):
    """Công thức gửi lên lớn bất thường."""


async def list_saved(db: AsyncPostgrestClient, query_text: str | None) -> list[SavedRecipe]:
    """Công thức đã lưu, mới nhất trước; q lọc theo tên món (không phân biệt hoa thường)."""
    query = db.table("saved_recipes").select(SAVED_COLUMNS).order("saved_at", desc=True)
    if query_text and query_text.strip():
        query = query.ilike("custom_payload->>title", f"%{escape_like(query_text.strip())}%")
    return [_saved_from_row(row) for row in (await query.execute()).data]


async def save_recipe(db: AsyncPostgrestClient, user_id: str, recipe: SuggestedRecipe) -> SavedRecipe:
    """Lưu công thức; đã lưu rồi thì ghi đè bản mới + đưa lên đầu danh sách (upsert theo recipe_id)."""
    payload = recipe.model_dump(mode="json")
    if len(json.dumps(payload, ensure_ascii=False)) > MAX_PAYLOAD_CHARS:
        raise PayloadTooLargeError("Công thức quá lớn, không lưu được")
    row = {"user_id": user_id, "recipe_id": recipe.recipe_id, "custom_payload": payload,
           "saved_at": datetime.now(timezone.utc).isoformat()}
    try:
        # upsert kèm select: 1 lượt, trả luôn diet_type từ bảng recipes (bảng nhúng)
        saved = await (
            db.table("saved_recipes").upsert(row, on_conflict="user_id,recipe_id").select(SAVED_COLUMNS).execute()
        )
    except APIError as error:
        if is_foreign_key_violation(error):
            raise InvalidReferenceError("Không tìm thấy công thức này") from error
        raise
    return _saved_from_row(saved.data[0])


async def delete_saved(db: AsyncPostgrestClient, saved_id: int) -> None:
    """Bỏ lưu; không thấy (hoặc của user khác) → NotFoundError."""
    if not (await db.table("saved_recipes").delete().eq("id", saved_id).execute()).data:
        raise NotFoundError("Không tìm thấy công thức đã lưu này")


def escape_like(text: str) -> str:
    """Để user gõ %, _ hay \\ được tìm đúng ký tự đó, không thành ký tự đại diện của LIKE."""
    for char in LIKE_SPECIAL_CHARS:
        text = text.replace(char, "\\" + char)
    return text


def _saved_from_row(row: dict[str, Any]) -> SavedRecipe:
    recipe_row = row.get("recipes") or {}
    return SavedRecipe(
        id=row["id"], recipe_id=row["recipe_id"], saved_at=row["saved_at"],
        diet_type=recipe_row.get("diet_type"), recipe=row["custom_payload"],
    )
