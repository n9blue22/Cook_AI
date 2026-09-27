"""Gia vị cơ bản luôn coi là có sẵn trong bếp: LLM bỏ khỏi bản chỉnh thì code cộng lại từ công thức gốc."""

from app.services.ingredient_normalizer import is_pantry_basic
from app.services.llm.recipe_adaptation import AdaptedIngredient, AdaptedRecipe
from app.services.recipe_repository import OriginalRecipe

# is_pantry_basic đã gồm nước, muối, tiêu, hạt nêm, bột ngọt; thêm 3 gia vị này ở đây, KHÔNG mở rộng is_pantry_basic
# vì nó còn quyết định % khớp lúc seed và cảnh báo nguyên liệu chưa nhận diện.
KITCHEN_STAPLE_NAMES = frozenset({"Đường", "Dầu ăn", "Nước mắm"})


def is_always_available(name_vi: str) -> bool:
    """Nước, muối, tiêu, đường, hạt nêm, bột ngọt, dầu ăn, nước mắm — user không cần tick trên màn Confirm."""
    return is_pantry_basic(name_vi) or name_vi in KITCHEN_STAPLE_NAMES


def restore_pantry_basics(adapted: AdaptedRecipe, original: OriginalRecipe) -> AdaptedRecipe:
    """Cộng lại gia vị cơ bản có trong công thức gốc mà LLM đã bỏ; lượng nhân theo tỉ lệ khẩu phần mới.
    Gọi TRƯỚC validation để dị ứng (vd nước mắm → cá) vẫn được kiểm tra."""
    kept_ids = {item.ingredient_id for item in adapted.ingredients}
    scale = adapted.servings / (original.hit.servings or 1)
    missing = [
        AdaptedIngredient(
            ingredient_id=item.ingredient_id,
            amount=None if item.amount is None else item.amount * scale,
            unit=item.unit,
        )
        for item in original.ingredients
        if item.ingredient_id not in kept_ids and is_always_available(item.name_vi)
    ]
    if not missing:
        return adapted
    return adapted.model_copy(update={"ingredients": [*adapted.ingredients, *missing]})
