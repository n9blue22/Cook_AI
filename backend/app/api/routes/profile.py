"""GET + PATCH /profile (feature-spec mục 6): chế độ ăn, dị ứng (slug), mục tiêu kcal. Cần đăng nhập."""

from fastapi import APIRouter, Depends
from postgrest import AsyncPostgrestClient

from app.api.deps import limit_user, user_db_dependency
from app.services.auth_tokens import CurrentUser
from app.services.profile_service import Profile, ProfileUpdate, get_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])
profile_user = limit_user("profile")  # 1 object dùng chung → FastAPI chỉ đếm rate limit 1 lần/request
profile_db = user_db_dependency(profile_user)


@router.get("", response_model=Profile)
async def read_profile(
    user: CurrentUser = Depends(profile_user), db: AsyncPostgrestClient = Depends(profile_db),
) -> Profile:
    """Hồ sơ của user đang đăng nhập."""
    return await get_profile(db, user.id)


@router.patch("", response_model=Profile)
async def patch_profile(
    changes: ProfileUpdate, user: CurrentUser = Depends(profile_user), db: AsyncPostgrestClient = Depends(profile_db),
) -> Profile:
    """Đổi các trường được gửi; allergens thay cả bộ."""
    return await update_profile(db, user.id, changes)
