"""POST / GET /logs (feature-spec mục 6): nhật ký dinh dưỡng theo ngày."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from postgrest import AsyncPostgrestClient

from app.api.deps import limit_user, user_db_dependency
from app.services.auth_tokens import CurrentUser
from app.services.meal_log_service import DaySummary, MealLogIn, add_meal_log, summarize_day, today_vn

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
) -> DaySummary:
    """Tổng kcal + macro của ngày ?date=YYYY-MM-DD (mặc định hôm nay, giờ VN)."""
    return await summarize_day(db, day or today_vn())
