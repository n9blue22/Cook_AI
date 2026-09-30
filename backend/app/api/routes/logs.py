"""POST / GET / DELETE /logs (feature-spec mục 6): nhật ký dinh dưỡng theo ngày."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from postgrest import AsyncPostgrestClient

from supabase import AsyncClient

from app.api.deps import get_admin_client, limit_user, user_db_dependency
from app.services.auth_tokens import CurrentUser
from app.services.meal_log_service import (
    DaySummary,
    MealLogIn,
    add_meal_log,
    delete_meal_log,
    summarize_day,
    today_vn,
)

router = APIRouter(prefix="/logs", tags=["logs"])
logs_user = limit_user("default_user")
logs_db = user_db_dependency(logs_user)


@router.post("", status_code=204)
async def create_meal_log(
    meal: MealLogIn, user: CurrentUser = Depends(logs_user), db: AsyncPostgrestClient = Depends(logs_db),
) -> Response:
    """Ghi 1 bữa vừa nấu xong."""
    await add_meal_log(db, user.id, meal)
    return Response(status_code=204)


@router.get("", response_model=DaySummary)
async def read_day_summary(
    day: date | None = Query(default=None, alias="date"), db: AsyncPostgrestClient = Depends(logs_db),
    admin: AsyncClient = Depends(get_admin_client),
) -> DaySummary:
    """Tổng kcal + macro và từng bữa (kèm tên món) của ngày ?date=YYYY-MM-DD (mặc định hôm nay, giờ VN)."""
    return await summarize_day(db, admin, day or today_vn())


@router.delete("/{log_id}", status_code=204)
async def remove_meal_log(log_id: int, db: AsyncPostgrestClient = Depends(logs_db)) -> Response:
    """Xoá 1 bữa ghi nhầm; chỉ bữa của chính user (RLS), không thấy → 404."""
    await delete_meal_log(db, log_id)
    return Response(status_code=204)
