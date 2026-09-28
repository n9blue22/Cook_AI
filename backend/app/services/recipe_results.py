"""Dựng công thức trả client (feature-spec mục 6): bản AI chỉnh đã validate hoặc bản gốc fallback.

Tên nguyên liệu, dinh dưỡng, thời gian nghỉ và cảnh báo đều tra từ công thức gốc trong DB, không lấy từ LLM.
"""

import logging
from typing import Literal

from pydantic import BaseModel, computed_field

from app.services.llm.recipe_adaptation import AdaptedRecipe, AdaptedStep
from app.services.nutrition import Nutrition, nutrition_per_serving
from app.services.recipe_repository import OriginalRecipe, RecipeLanguage
from app.services.validation import SafetyRule, check_cooking_safety, is_cooking_step, max_rest_sec

logger = logging.getLogger(__name__)

RecipeSource = Literal["adapted", "original"]
UNMAPPED_INGREDIENTS_WARNING = (
    "Một số nguyên liệu trong công thức gốc chưa được hệ thống nhận diện đầy đủ — kiểm tra chín kỹ trước khi ăn"
)
RAW_INGREDIENT_NOTE = (
    "Món này dùng nguyên liệu sống hoặc chưa nấu chín — đảm bảo nguồn sạch, "
    "không phù hợp cho trẻ nhỏ/phụ nữ mang thai/người miễn dịch yếu."
)


class RecipeIngredientOut(BaseModel):
    """Nguyên liệu trả client; amount/unit None khi công thức gốc không ghi lượng."""

    ingredient_id: int
    name: str
    amount: float | None
    unit: str | None


class SuggestedRecipe(BaseModel):
    """Một công thức trả client; source cho biết LLM đã chỉnh (adapted) hay fallback về bản gốc (original)."""

    recipe_id: int
    source: RecipeSource
    title: str
    servings: int
    ingredients: list[RecipeIngredientOut]
    steps: list[AdaptedStep]
    rest_sec: int
    nutrition_per_serving: Nutrition | None  # luôn tính bằng code từ nutrition_facts; None khi gốc không có gram
    score: float
    has_unmapped_ingredients: bool  # không chặn món, chỉ cảnh báo (nguyên liệu lạ không qua được validation)
    # Thời gian chuẩn bị của công thức gốc (recipes.prep_minutes). Có mặc định: payload POST /saved của client cũ
    # và custom_payload đã lưu trước khi có field này không mang nó → thiếu thì 422 / không đọc lại được.
    prep_minutes: int | None = None
    language: RecipeLanguage = "vi"  # "en" = bản gốc Food.com, client gắn nhãn thay vì dịch
    # Bản gốc cũng không đạt ngưỡng nấu chín (món chủ đích dùng đồ sống) — không chặn, chỉ cảnh báo.
    # Bản adapted luôn False (đã qua validation).
    raw_ingredient_warning: bool = False

    @computed_field
    @property
    def nutrition_available(self) -> bool:
        """False = có nguyên liệu bắt buộc thiếu lượng gram → không trả số (không cộng thiếu rồi trả như đủ)."""
        return self.nutrition_per_serving is not None

    @computed_field
    @property
    def raw_ingredient_note(self) -> str | None:
        """Dòng cảnh báo client hiển thị khi raw_ingredient_warning."""
        return RAW_INGREDIENT_NOTE if self.raw_ingredient_warning else None

    @computed_field
    @property
    def unmapped_ingredients_warning(self) -> str | None:
        """Dòng cảnh báo client hiển thị kèm công thức (cùng kiểu disclaimer ảnh AI)."""
        return UNMAPPED_INGREDIENTS_WARNING if self.has_unmapped_ingredients else None


def rules_by_ingredient(original: OriginalRecipe) -> dict[int, SafetyRule]:
    """ingredient_id → SafetyRule của các nguyên liệu cần nấu chín trong công thức gốc."""
    return {item.ingredient_id: item.safety_rule for item in original.ingredients if item.safety_rule}


def nutrition_from_original(original: OriginalRecipe, kept_ids: set[int]) -> Nutrition | None:
    """Dinh dưỡng/suất tính từ gram + nutrition_facts của công thức GỐC, chỉ các nguyên liệu còn giữ.

    Không dùng amount của LLM: chia theo servings gốc cho ra số/suất — không đổi khi LLM nhân khẩu phần.
    Bất kỳ nguyên liệu bắt buộc nào thiếu gram hoặc thiếu nutrition_facts → None cho cả món: cộng thiếu rồi trả
    như đủ là số sai (vd trứng ngâm mật ong ra 304 kcal / 0 g đạm vì trứng không ghi gram).
    """
    kept = [item for item in original.ingredients if item.ingredient_id in kept_ids]
    if not kept or any(not (item.grams and item.facts_per_100g) for item in kept if not item.is_optional):
        return None
    grams = {item.ingredient_id: item.grams for item in kept if item.grams and item.facts_per_100g}
    facts = {item.ingredient_id: item.facts_per_100g for item in kept if item.facts_per_100g}
    return nutrition_per_serving(grams, facts, original.hit.servings)


def fails_cooking_safety(original: OriginalRecipe) -> bool:
    """Công thức gốc CÓ ghi bước nấu (nhiệt độ + thời gian) mà vẫn không đạt ngưỡng (cùng kiểm tra validation áp cho
    bản AI chỉnh). Gốc không ghi bước nấu nào → False: "chưa biết" khác "không an toàn" — hiện recipe_steps gốc chưa
    seed nhiệt độ nên không món nào bị gắn (TODO feature-spec mục 9).
    """
    if not any(is_cooking_step(step) for step in original.steps):
        return False
    ingredient_ids = [item.ingredient_id for item in original.ingredients]
    return check_cooking_safety(ingredient_ids, original.steps, rules_by_ingredient(original)) is not None


def original_result(original: OriginalRecipe) -> SuggestedRecipe:
    """Công thức gốc đã kiểm duyệt, không qua LLM; gốc không đạt ngưỡng nấu chín thì gắn cảnh báo, không chặn."""
    ingredient_ids = [item.ingredient_id for item in original.ingredients]
    raw_warning = fails_cooking_safety(original)
    if raw_warning:
        logger.info("Recipe %d: bản gốc không có bước nấu đạt ngưỡng — kèm raw_ingredient_warning", original.hit.recipe_id)
    return SuggestedRecipe(
        recipe_id=original.hit.recipe_id,
        source="original",
        title=original.hit.title,
        servings=original.hit.servings,
        ingredients=[
            RecipeIngredientOut(ingredient_id=item.ingredient_id, name=item.name_vi, amount=item.amount, unit=item.unit)
            for item in original.ingredients
        ],
        steps=original.steps,
        rest_sec=max_rest_sec(ingredient_ids, rules_by_ingredient(original)),
        nutrition_per_serving=nutrition_from_original(original, set(ingredient_ids)),
        score=original.hit.score,
        has_unmapped_ingredients=original.hit.has_unmapped_ingredients,
        prep_minutes=original.hit.prep_minutes,
        language=original.hit.original_language,
        raw_ingredient_warning=raw_warning,
    )


def adapted_result(original: OriginalRecipe, adapted: AdaptedRecipe) -> SuggestedRecipe:
    """Công thức LLM đã chỉnh + đã validate; tên nguyên liệu và dinh dưỡng lấy từ DB."""
    names = {item.ingredient_id: item.name_vi for item in original.ingredients}
    return SuggestedRecipe(
        recipe_id=original.hit.recipe_id,
        source="adapted",
        title=adapted.title,
        servings=adapted.servings,
        ingredients=[
            RecipeIngredientOut(
                ingredient_id=item.ingredient_id, name=names[item.ingredient_id], amount=item.amount, unit=item.unit,
            )
            for item in adapted.ingredients
        ],
        steps=adapted.steps,
        rest_sec=adapted.rest_sec,
        nutrition_per_serving=nutrition_from_original(original, {item.ingredient_id for item in adapted.ingredients}),
        score=original.hit.score,
        has_unmapped_ingredients=original.hit.has_unmapped_ingredients,
        prep_minutes=original.hit.prep_minutes,
    )
