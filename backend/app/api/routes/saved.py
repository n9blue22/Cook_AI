"""GET / POST / DELETE /saved (feature-spec mục 6): công thức đã lưu, tìm theo tên bằng ?q=."""

from fastapi import APIRouter, Depends, Query, Response
from postgrest import AsyncPostgrestClient

from app.api.deps import limit_user, user_db_dependency
from app.services.auth_tokens import CurrentUser
from app.services.saved_recipe_service import (
    MAX_QUERY_LENGTH,
    SavedRecipe,
    SaveRecipeIn,
    delete_saved,
    list_saved,
    save_recipe,
)

router = APIRouter(prefix="/saved", tags=["saved"])
saved_user = limit_user("default_user")
saved_db = user_db_dependency(saved_user)


@router.get("", response_model=list[SavedRecipe])
async def read_saved(
    q: str | None = Query(default=None, max_length=MAX_QUERY_LENGTH), db: AsyncPostgrestClient = Depends(saved_db),
) -> list[SavedRecipe]:
    """Công thức đã lưu, mới nhất trước."""
    return await list_saved(db, q)


@router.post("", response_model=SavedRecipe, status_code=201)
async def create_saved(
    body: SaveRecipeIn, user: CurrentUser = Depends(saved_user), db: AsyncPostgrestClient = Depends(saved_db),
) -> SavedRecipe:
    """Lưu (hoặc lưu lại bản mới) 1 công thức."""
    return await save_recipe(db, user.id, body.recipe)


@router.delete("/{saved_id}", status_code=204)
async def remove_saved(saved_id: int, db: AsyncPostgrestClient = Depends(saved_db)) -> Response:
    """Bỏ lưu 1 công thức."""
    await delete_saved(db, saved_id)
    return Response(status_code=204)
