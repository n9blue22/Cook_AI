"""Tủ lạnh ảo (feature-spec P1#11): nguyên liệu user đang có. Client DB mang JWT của user → RLS owner-only."""

from datetime import date
from typing import Any, Self

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, model_validator

from app.services.ingredient_matching import CatalogIngredient
from app.services.ingredient_normalizer import (
    IngredientMatch,
    IngredientNormalizer,
    MatchStatus,
    load_ingredient_catalog,
)
from app.services.user_data_errors import InvalidReferenceError, NotFoundError, is_foreign_key_violation

PANTRY_COLUMNS = "id,ingredient_id,quantity,unit,expires_on,ingredients(name_vi)"
MAX_NAME_LENGTH = 100
MAX_UNIT_LENGTH = 20
MAX_QUANTITY = 99_999_999  # numeric(10, 2)
MAX_BATCH_ITEMS = 50
UPSERT_CONFLICT_COLUMNS = "user_id,ingredient_id"


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


class PantryBatchIn(BaseModel):
    """POST /pantry/batch: 1–MAX_BATCH_ITEMS mục, mỗi mục cùng luật với POST /pantry."""

    items: list[PantryItemIn] = Field(min_length=1, max_length=MAX_BATCH_ITEMS)


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
        # upsert kèm select: 1 lượt, trả luôn dòng đã ghi kèm tên nguyên liệu (bảng nhúng)
        [saved] = await _upsert_returning_rows(db, [row])
    except APIError as error:
        if is_foreign_key_violation(error):
            raise InvalidReferenceError("Không có nguyên liệu này trong danh mục") from error
        raise
    return _item_from_row(saved)


class PantryBatchResult(BaseModel):
    """Kết quả POST /pantry/batch: các dòng đã ghi + các mục bị bỏ qua (không làm hỏng cả lô)."""

    items: list[PantryItem]
    unmatched_names: list[str]  # tên gõ tay không khớp chắc chắn nguyên liệu nào
    unknown_ids: list[int]  # ingredient_id không có trong danh mục


async def add_pantry_items(
    db: AsyncPostgrestClient, user_id: str, batch: PantryBatchIn, catalog: list[CatalogIngredient],
) -> PantryBatchResult:
    """Thêm / cập nhật nhiều nguyên liệu bằng 1 lượt upsert; tên và id kiểm qua danh mục (cache), mục không hợp lệ
    trả về danh sách riêng. Trùng nguyên liệu trong lô → gộp, mục sau ghi đè các trường nó gửi."""
    fields_by_id, unmatched_names, unknown_ids = _resolve_batch(batch.items, catalog)
    if not fields_by_id:
        return PantryBatchResult(items=[], unmatched_names=unmatched_names, unknown_ids=unknown_ids)
    rows = await _rows_keeping_unsent_fields(db, user_id, fields_by_id)
    try:
        saved = await _upsert_returning_rows(db, rows)
    except APIError as error:
        if is_foreign_key_violation(error):  # danh mục vừa đổi sau khi cache nạp
            raise InvalidReferenceError("Có nguyên liệu không còn trong danh mục, thử lại") from error
        raise
    by_ingredient = {row["ingredient_id"]: _item_from_row(row) for row in saved}
    items = [by_ingredient[ingredient_id] for ingredient_id in fields_by_id]
    return PantryBatchResult(items=items, unmatched_names=unmatched_names, unknown_ids=unknown_ids)


async def _upsert_returning_rows(db: AsyncPostgrestClient, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """1 lượt: upsert theo (user_id, ingredient_id) kèm select → trả dòng đã ghi có tên nguyên liệu (bảng nhúng)."""
    query = db.table("pantry_items").upsert(rows, on_conflict=UPSERT_CONFLICT_COLUMNS).select(PANTRY_COLUMNS)
    return (await query.execute()).data


def _resolve_batch(
    items: list[PantryItemIn], catalog: list[CatalogIngredient],
) -> tuple[dict[int, dict[str, Any]], list[str], list[int]]:
    """Mục → (ingredient_id → các trường đã gửi, giữ thứ tự gặp đầu), tên không khớp, id không có trong danh mục."""
    known_ids = {ingredient.id for ingredient in catalog}
    names = [item.name for item in items if item.name is not None]
    matches = iter(IngredientNormalizer(catalog).normalize(names)) if names else iter(())
    fields_by_id: dict[int, dict[str, Any]] = {}
    unmatched_names: list[str] = []
    unknown_ids: list[int] = []
    for item in items:
        ingredient_id = item.ingredient_id if item.name is None else _accepted_id(next(matches))
        if item.name is not None and ingredient_id is None:
            unmatched_names.append(item.name)
        elif ingredient_id not in known_ids:
            unknown_ids.append(ingredient_id)
        else:
            sent = item.model_dump(mode="json", exclude_unset=True, exclude={"ingredient_id", "name"})
            fields_by_id.setdefault(ingredient_id, {}).update(sent)
    return fields_by_id, unmatched_names, unknown_ids


def _accepted_id(match: IngredientMatch) -> int | None:
    return match.ingredient_id if match.status is MatchStatus.ACCEPTED else None


async def _rows_keeping_unsent_fields(
    db: AsyncPostgrestClient, user_id: str, fields_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Upsert nhiều dòng dùng chung 1 bộ cột (hợp các trường đã gửi) — mục không gửi trường nào đó sẽ bị ghi null.
    Khi các mục gửi khác trường, lấy giá trị đang có trong tủ cho phần thiếu (1 lượt đọc), giống POST /pantry."""
    columns = sorted({column for fields in fields_by_id.values() for column in fields})
    current: dict[int, dict[str, Any]] = {}
    if any(len(fields) < len(columns) for fields in fields_by_id.values()):
        query = (
            db.table("pantry_items").select(",".join(["ingredient_id", *columns]))
            .in_("ingredient_id", list(fields_by_id))
        )
        current = {row.pop("ingredient_id"): row for row in (await query.execute()).data}
    return [
        {"user_id": user_id, "ingredient_id": ingredient_id,
         **{column: current.get(ingredient_id, {}).get(column) for column in columns}, **fields}
        for ingredient_id, fields in fields_by_id.items()
    ]


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
