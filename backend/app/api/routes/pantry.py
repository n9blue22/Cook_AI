"""GET / POST / DELETE /pantry (feature-spec mục 6): tủ lạnh ảo của user đang đăng nhập."""

from fastapi import APIRouter, Depends, Response
from postgrest import AsyncPostgrestClient

from app.api.deps import limit_user, user_db_dependency
from app.services.auth_tokens import CurrentUser
from app.services.pantry_service import PantryItem, PantryItemIn, add_pantry_item, list_pantry, remove_pantry_item

router = APIRouter(prefix="/pantry", tags=["pantry"])
pantry_user = limit_user("default_user")
pantry_db = user_db_dependency(pantry_user)


@router.get("", response_model=list[PantryItem])
async def read_pantry(db: AsyncPostgrestClient = Depends(pantry_db)) -> list[PantryItem]:
    """Nguyên liệu đang có, sắp hết hạn lên trước."""
    return await list_pantry(db)


@router.post("", response_model=PantryItem, status_code=201)
async def create_pantry_item(
    item: PantryItemIn, user: CurrentUser = Depends(pantry_user), db: AsyncPostgrestClient = Depends(pantry_db),
) -> PantryItem:
    """Thêm (hoặc cập nhật nếu đã có) 1 nguyên liệu."""
    return await add_pantry_item(db, user.id, item)


@router.delete("/{item_id}", status_code=204)
async def delete_pantry_item(item_id: int, db: AsyncPostgrestClient = Depends(pantry_db)) -> Response:
    """Bỏ 1 nguyên liệu khỏi tủ."""
    await remove_pantry_item(db, item_id)
    return Response(status_code=204)
