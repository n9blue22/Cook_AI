"""Hồ sơ user (chế độ ăn, dị ứng theo slug, mục tiêu kcal) — đọc/ghi bằng client mang JWT của user (RLS owner-only)."""

from pydantic import BaseModel, Field
from postgrest import AsyncPostgrestClient

from app.services.diet_types import AllergenSlug, DietType

MIN_KCAL_GOAL = 800
MAX_KCAL_GOAL = 6000
PROFILE_COLUMNS = "diet_type,daily_kcal_goal"


class Profile(BaseModel):
    """Hồ sơ trả client."""

    diet_type: DietType
    daily_kcal_goal: int | None
    allergens: list[AllergenSlug]


class ProfileUpdate(BaseModel):
    """PATCH /profile: chỉ trường nào gửi lên mới đổi; daily_kcal_goal = null để bỏ mục tiêu."""

    diet_type: DietType | None = None
    daily_kcal_goal: int | None = Field(default=None, ge=MIN_KCAL_GOAL, le=MAX_KCAL_GOAL)
    allergens: list[AllergenSlug] | None = None


async def get_profile(db: AsyncPostgrestClient, user_id: str) -> Profile:
    """Hồ sơ của user; thiếu dòng (user có trước trigger) thì tạo mặc định."""
    rows = (await db.table("user_profiles").select(PROFILE_COLUMNS).eq("user_id", user_id).execute()).data
    if not rows:
        await db.table("user_profiles").upsert({"user_id": user_id}, ignore_duplicates=True).execute()
        rows = [{"diet_type": "omnivore", "daily_kcal_goal": None}]
    links = (await db.table("user_allergens").select("allergens(slug)").eq("user_id", user_id).execute()).data
    return Profile(**rows[0], allergens=sorted(link["allergens"]["slug"] for link in links))


async def update_profile(db: AsyncPostgrestClient, user_id: str, changes: ProfileUpdate) -> Profile:
    """Ghi các trường được gửi; danh sách dị ứng thay cả bộ trong 1 giao dịch (RPC set_my_allergens)."""
    fields = changes.model_dump(exclude_unset=True, exclude={"allergens"})
    if "diet_type" in fields and fields["diet_type"] is None:
        del fields["diet_type"]  # diet_type bắt buộc có giá trị, null = không đổi
    if fields:
        await db.table("user_profiles").update(fields).eq("user_id", user_id).execute()
    if changes.allergens is not None:
        await db.rpc("set_my_allergens", {"p_slugs": sorted(set(changes.allergens))}).execute()
    return await get_profile(db, user_id)
