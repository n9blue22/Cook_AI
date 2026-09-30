"""Nhật ký dinh dưỡng (feature-spec P1#12): "Đã nấu xong" → ghi kcal + macro; tổng hợp theo ngày giờ Việt Nam."""

from datetime import date, datetime, time, timedelta

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field
from supabase import AsyncClient

from app.services.rate_limit import VN_TZ
from app.services.user_data_errors import InvalidReferenceError, NotFoundError, is_foreign_key_violation

MAX_KCAL = 99_999  # numeric(7, 2)
MAX_MACRO_G = 9_999  # numeric(6, 2)
SUM_COLUMNS = ("kcal", "protein_g", "carb_g", "fat_g")
ENTRY_COLUMNS = ("id", "recipe_id", *SUM_COLUMNS, "logged_at")


class MealLogIn(BaseModel):
    """POST /logs: số liệu 1 phần ăn — client gửi lại đúng nutrition_per_serving backend đã tính từ nutrition_facts.
    RLS vốn cho user ghi thẳng nhật ký của chính mình, nên tính lại ở đây không thêm lớp bảo vệ nào."""

    recipe_id: int | None = None
    kcal: float = Field(ge=0, le=MAX_KCAL)
    protein_g: float = Field(ge=0, le=MAX_MACRO_G)
    carb_g: float = Field(ge=0, le=MAX_MACRO_G)
    fat_g: float = Field(ge=0, le=MAX_MACRO_G)


class MealLogEntry(BaseModel):
    """1 bữa đã ghi, kèm tên gốc của món."""

    id: int
    recipe_id: int | None  # None khi công thức đã bị xoá (on delete set null)
    title: str | None  # None khi recipe_id None
    kcal: float
    protein_g: float
    carb_g: float
    fat_g: float
    logged_at: datetime


class DaySummary(BaseModel):
    """Tổng dinh dưỡng 1 ngày (giờ VN) + từng bữa, cũ trước."""

    date: date
    kcal: float
    protein_g: float
    carb_g: float
    fat_g: float
    meals: int
    entries: list[MealLogEntry]


def today_vn() -> date:
    """Ngày hiện tại theo giờ Việt Nam (mặc định của GET /logs)."""
    return datetime.now(VN_TZ).date()


async def add_meal_log(db: AsyncPostgrestClient, user_id: str, meal: MealLogIn) -> None:
    """Ghi 1 bữa vào nhật ký, thời điểm = lúc ghi."""
    try:
        await db.table("meal_logs").insert({"user_id": user_id, **meal.model_dump()}).execute()
    except APIError as error:
        if is_foreign_key_violation(error):
            raise InvalidReferenceError("Không tìm thấy công thức này") from error
        raise


async def summarize_day(db: AsyncPostgrestClient, admin: AsyncClient, day: date) -> DaySummary:
    """Các bữa trong ngày `day` (00:00 → 24:00 giờ VN) của user đang đăng nhập (RLS) + tổng."""
    start = datetime.combine(day, time.min, tzinfo=VN_TZ)
    query = db.table("meal_logs").select(",".join(ENTRY_COLUMNS)).gte("logged_at", start.isoformat()).lt(
        "logged_at", (start + timedelta(days=1)).isoformat(),
    ).order("logged_at")
    rows = (await query.execute()).data
    titles = await recipe_titles(admin, {row["recipe_id"] for row in rows if row["recipe_id"] is not None})
    totals = {column: round(sum(float(row[column]) for row in rows), 1) for column in SUM_COLUMNS}
    entries = [MealLogEntry(**row, title=titles.get(row["recipe_id"])) for row in rows]
    return DaySummary(date=day, meals=len(rows), entries=entries, **totals)


async def recipe_titles(admin: AsyncClient, recipe_ids: set[int]) -> dict[int, str]:
    """Tên gốc theo recipe_id. Đọc bằng admin: RLS chỉ cho user đọc món đã kiểm duyệt, món Food.com sẽ mất tên.
    Chỉ tra đúng id lấy từ nhật ký của chính user nên không lộ gì thêm."""
    if not recipe_ids:
        return {}
    rows = (await admin.table("recipes").select("id,title").in_("id", sorted(recipe_ids)).execute()).data
    return {row["id"]: row["title"] for row in rows}


async def delete_meal_log(db: AsyncPostgrestClient, log_id: int) -> None:
    """Xoá 1 bữa; không thấy hoặc của user khác (RLS lọc mất) → NotFoundError."""
    if not (await db.table("meal_logs").delete().eq("id", log_id).execute()).data:
        raise NotFoundError("Không tìm thấy bữa này trong nhật ký")
