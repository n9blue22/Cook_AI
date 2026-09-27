"""Tủ lạnh ảo (feature-spec P1#11): nguyên liệu user đang có. Client DB mang JWT của user → RLS owner-only."""

from datetime import date
from typing import Any, Self

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, model_validator

from app.services.ingredient_normalizer import IngredientNormalizer, MatchStatus, load_ingredient_catalog
from app.services.user_data_errors import InvalidReferenceError, NotFoundError, is_foreign_key_violation

PANTRY_COLUMNS = "id,ingredient_id,quantity,unit,expires_on,ingredients(name_vi)"
MAX_NAME_LENGTH = 100
MAX_UNIT_LENGTH = 20
MAX_QUANTITY = 99_999_999  # numeric(10, 2)


class PantryItemIn(BaseModel):
    """POST /pantry: ingredient_id (đã map sẵn, vd từ /recognize) hoặc name (user gõ tay) — đúng 1 trong 2."""

    ingredient_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME_LENGTH)
    quantity: float | None = Field(default=None, ge=0, le=MAX_QUANTITY)
    unit: str | None = Field(default=None, max_length=MAX_UNIT_LENGTH)
    expires_on: date | None = None

    @model_validator(mode="after")
    def exactly_one_reference(self) -> Self:
        if (self.ingredient_id is None) == (self.name is None):
            raise ValueError("Gửi đúng 1 trong 2: ingredient_id hoặc name")
        return self


class PantryItem(BaseModel):
    """1 nguyên liệu trong tủ trả client."""

    id: int
    ingredient_id: int
    name: str
    quantity: float | None
    unit: str | None
    expires_on: date | None


async def list_pantry(db: AsyncPostgrestClient) -> list[PantryItem]:
    """Tủ của user, món sắp hết hạn lên trước, món không ghi hạn xuống cuối."""
    query = db.table("pantry_items").select(PANTRY_COLUMNS).order("expires_on", nullsfirst=False).order("id")
    return [_item_from_row(row) for row in (await query.execute()).data]


async def add_pantry_item(db: AsyncPostgrestClient, user_id: str, item: PantryItemIn) -> PantryItem:
    """Thêm vào tủ; nguyên liệu đã có thì chỉ cập nhật các trường được gửi (upsert, không nhân đôi)."""
    ingredient_id = item.ingredient_id if item.ingredient_id is not None else await _resolve_name(db, item.name)
    row = {"user_id": user_id, "ingredient_id": ingredient_id, **item.model_dump(
        mode="json", exclude_unset=True, exclude={"ingredient_id", "name"},
    )}
    try:
        saved = (await db.table("pantry_items").upsert(row, on_conflict="user_id,ingredient_id").execute()).data[0]
    except APIError as error:
        if is_foreign_key_violation(error):
            raise InvalidReferenceError("Không có nguyên liệu này trong danh mục") from error
        raise
    fresh = await db.table("pantry_items").select(PANTRY_COLUMNS).eq("id", saved["id"]).execute()
    return _item_from_row(fresh.data[0])


async def remove_pantry_item(db: AsyncPostgrestClient, item_id: int) -> None:
    """Xoá 1 món khỏi tủ; không thấy (hoặc của user khác) → NotFoundError."""
    if not (await db.table("pantry_items").delete().eq("id", item_id).execute()).data:
        raise NotFoundError("Không tìm thấy nguyên liệu này trong tủ")


async def _resolve_name(db: AsyncPostgrestClient, name: str) -> int:
    """Tên gõ tay → ingredient_id; chỉ nhận khi khớp chắc chắn, không tự đoán món gần giống."""
    catalog = await load_ingredient_catalog(db)  # type: ignore[arg-type]  # chỉ dùng .table(), 2 client như nhau
    match = IngredientNormalizer(catalog).normalize([name])[0]
    if match.status is not MatchStatus.ACCEPTED or match.ingredient_id is None:
        raise InvalidReferenceError(f"Chưa nhận ra nguyên liệu “{name}” — thử tên khác")
    return match.ingredient_id


def _item_from_row(row: dict[str, Any]) -> PantryItem:
    return PantryItem(**{key: value for key, value in row.items() if key != "ingredients"}, name=row["ingredients"]["name_vi"])
