"""Cờ nguyên liệu sống theo tên món (tái, sống, ceviche…) và bước Food.com "rare" — độc lập với cờ dò bước nấu."""

import pytest

from app.services.llm.recipe_adaptation import AdaptedStep
from app.services.recipe_repository import OriginalRecipe, RecipeIngredientInfo, SearchHit
from app.services.recipe_results import original_result
from app.services.validation import safety_rule_from_row

BEEF = safety_rule_from_row({"category": "whole_cut", "min_temp_c": 63, "min_duration_sec": 0, "rest_sec": 180})
BEEF_ID, LIME_ID = 1, 2
FOODCOM_URL = "https://www.food.com/recipe/1"


def recipe(title: str, step: str, with_meat: bool = True, source_url: str | None = None) -> OriginalRecipe:
    """Món có 1 bước làm nóng (cờ cũ không bật) — chỉ tên món / bước "rare" quyết định cờ mới."""
    ingredients = [RecipeIngredientInfo(LIME_ID, "Chanh", None, None, None, frozenset(), None)]
    if with_meat:
        ingredients.append(RecipeIngredientInfo(BEEF_ID, "Thịt bò", None, None, BEEF, frozenset(), None))
    return OriginalRecipe(
        hit=SearchHit(recipe_id=1, title=title, servings=2, score=0.5, source_url=source_url),
        ingredients=ingredients,
        steps=[AdaptedStep(step_no=1, action=step, temperature_c=None, duration_sec=None)],
    )


@pytest.mark.parametrize("title", [
    "Bò Tái Chanh Tự Làm Tại Nhà", "Gỏi Rau Càng Cua Bò Tái Lăn", "Tôm Sống Sốt Thái", "Bún Bò Tái",
    "shrimp ceviche with avocado",
])
def test_raw_dish_title_gets_warning_even_with_a_heating_step(title: str) -> None:
    assert original_result(recipe(title, "Phi thơm tỏi rồi nấu nước dùng.")).raw_ingredient_warning


@pytest.mark.parametrize("title", ["Gỏi cuốn tôm thịt", "Tôm Luộc", "Gà Xé Phay", "Nụ bí bọc giò sống"])
def test_cooked_dish_title_has_no_warning(title: str) -> None:
    # Bước tiếng Việt có "sống"/"tái" (tả nguyên liệu trước khi nấu) không được tính.
    cooked = recipe(title, "Tôm sống bóc vỏ, luộc chín; thịt xào tái rồi đảo chín.")
    assert not original_result(cooked).raw_ingredient_warning


def test_raw_dish_title_without_meat_fish_or_egg_has_no_warning() -> None:
    assert not original_result(recipe("Bò Tái Chanh chay", "Nấu nước dùng.", with_meat=False)).raw_ingredient_warning


def test_foodcom_step_cooking_to_rare_gets_warning() -> None:
    steak = recipe("peppery beef tenderloin", "roast 25 minutes for medium-rare", source_url=FOODCOM_URL)
    assert original_result(steak).raw_ingredient_warning


def test_foodcom_step_mentioning_raw_has_no_warning() -> None:
    chicken = recipe("grilled lime chicken", "place raw chicken on the grill and cook through", source_url=FOODCOM_URL)
    assert not original_result(chicken).raw_ingredient_warning
