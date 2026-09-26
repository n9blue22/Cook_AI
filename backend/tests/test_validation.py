"""Lớp validation 3: mỗi kiểm tra có test fail riêng + giả lập LLM "không nghe lời".

Ngưỡng an toàn KHÔNG hardcode trong test: đọc từ FOOD_SAFETY_THRESHOLDS — đúng dữ liệu seed_food_safety ghi vào
bảng food_safety (test cuối đối chiếu với bảng thật). Đổi ngưỡng trong bảng → kết quả test đổi theo.
Số liệu trong test (75°C, 480s...) là dữ liệu CÔNG THỨC, không phải ngưỡng.
"""

import asyncio
import dataclasses
import os

import pytest
from pydantic import BaseModel

from app.services.llm.groq_adapter import to_groq_strict_schema
from app.services.llm.provider import LLMProvider
from app.services.llm.recipe_adaptation import AdaptedIngredient, AdaptedRecipe, AdaptedStep
from app.services.validation import (
    ValidationContext,
    safety_rule_from_row,
    validate_adapted_recipe,
    with_rest_time,
)
from scripts.seed_food_safety import FOOD_SAFETY_THRESHOLDS

RULES = {row["category"]: safety_rule_from_row(row) for row in FOOD_SAFETY_THRESHOLDS}

CHICKEN_ID, LEMONGRASS_ID, FISH_SAUCE_ID, OIL_ID, CILANTRO_ID, BEEF_ID = 93, 18, 157, 148, 51, 80
RULE_BY_INGREDIENT = {CHICKEN_ID: RULES["poultry"], BEEF_ID: RULES["whole_cut"]}

CONTEXT = ValidationContext(
    allowed_ingredient_ids=frozenset({CHICKEN_ID, LEMONGRASS_ID, FISH_SAUCE_ID, OIL_ID, CILANTRO_ID}),
    user_allergens=frozenset(),
    allergens_by_ingredient={FISH_SAUCE_ID: frozenset({"fish"})},
    safety_rule_by_ingredient=RULE_BY_INGREDIENT,
)

PREP = AdaptedStep(step_no=1, action="Thái gà, băm sả.", temperature_c=None, duration_sec=None)
STIR_FRY_CHICKEN = AdaptedStep(step_no=2, action="Xào gà với sả đến chín.", temperature_c=75, duration_sec=480)
PLATE = AdaptedStep(step_no=3, action="Bày ra đĩa.", temperature_c=None, duration_sec=None)

VALID_RECIPE = AdaptedRecipe(
    title="Gà xào sả",
    servings=4,
    ingredients=[
        AdaptedIngredient(ingredient_id=CHICKEN_ID, amount=600, unit="g"),
        AdaptedIngredient(ingredient_id=LEMONGRASS_ID, amount=6, unit="cây"),
        AdaptedIngredient(ingredient_id=FISH_SAUCE_ID, amount=4, unit="muỗng canh"),
        AdaptedIngredient(ingredient_id=OIL_ID, amount=4, unit="muỗng canh"),
    ],
    steps=[PREP, STIR_FRY_CHICKEN, PLATE],
)

SEARED_BEEF = AdaptedRecipe(
    title="Bò áp chảo",
    servings=1,
    ingredients=[AdaptedIngredient(ingredient_id=BEEF_ID, amount=200, unit="g")],
    steps=[AdaptedStep(step_no=1, action="Áp chảo miếng bò mỗi mặt 1 phút.", temperature_c=63, duration_sec=120)],
)
BEEF_CONTEXT = dataclasses.replace(CONTEXT, allowed_ingredient_ids=frozenset({BEEF_ID}))


def with_steps(*steps: AdaptedStep) -> AdaptedRecipe:
    """VALID_RECIPE nhưng thay danh sách bước."""
    return VALID_RECIPE.model_copy(update={"steps": list(steps)})


def test_valid_recipe_passes() -> None:
    assert validate_adapted_recipe(VALID_RECIPE, CONTEXT) is None


def test_rejects_ingredient_outside_original_recipe() -> None:
    beef = AdaptedIngredient(ingredient_id=BEEF_ID, amount=200, unit="g")
    added_beef = VALID_RECIPE.model_copy(update={"ingredients": [*VALID_RECIPE.ingredients, beef]})
    reason = validate_adapted_recipe(added_beef, CONTEXT)
    assert reason is not None and str(BEEF_ID) in reason


def test_rejects_user_allergen() -> None:
    fish_allergic = dataclasses.replace(CONTEXT, user_allergens=frozenset({"fish"}))
    reason = validate_adapted_recipe(VALID_RECIPE, fish_allergic)
    assert reason is not None and "fish" in reason


def test_rejects_chicken_cooked_below_safe_temperature() -> None:
    undercooked = STIR_FRY_CHICKEN.model_copy(update={"temperature_c": 50})
    reason = validate_adapted_recipe(with_steps(PREP, undercooked, PLATE), CONTEXT)
    assert reason is not None and "poultry" in reason


def test_rejects_cooking_step_shorter_than_min_duration() -> None:
    whole_cut = RULES["whole_cut"]
    assert whole_cut.min_duration_sec > 0, "bảng food_safety không còn nhóm nào có thời gian giữ > 0"
    too_short = AdaptedStep(step_no=1, action="Áp chảo bò.", temperature_c=whole_cut.min_temp_c,
                            duration_sec=whole_cut.min_duration_sec - 1)
    reason = validate_adapted_recipe(SEARED_BEEF.model_copy(update={"steps": [too_short]}), BEEF_CONTEXT)
    assert reason is not None and f"≥{whole_cut.min_duration_sec}s" in reason


def test_rejects_recipe_with_protein_but_all_cooking_steps_removed() -> None:
    reason = validate_adapted_recipe(with_steps(PREP, PLATE), CONTEXT)
    assert reason is not None and "không còn bước nấu" in reason


def test_rejects_recipe_without_steps() -> None:
    assert validate_adapted_recipe(with_steps(), CONTEXT) is not None


def test_raw_salad_without_protein_needs_no_cooking_step() -> None:
    salad = AdaptedRecipe(
        title="Gỏi sả", servings=1, ingredients=[AdaptedIngredient(ingredient_id=LEMONGRASS_ID, amount=2, unit="cây")],
        steps=[PREP],
    )
    assert validate_adapted_recipe(salad, CONTEXT) is None


def test_seared_beef_two_minutes_passes_because_rest_is_not_cooking_time() -> None:
    # Trước khi tách rest_sec: whole_cut đòi bước nấu ≥180s → món này bị reject sai.
    assert validate_adapted_recipe(SEARED_BEEF, BEEF_CONTEXT) is None


def test_rest_time_comes_from_food_safety_not_from_llm() -> None:
    assert "rest_sec" not in to_groq_strict_schema(AdaptedRecipe)["properties"]
    assert with_rest_time(SEARED_BEEF, RULE_BY_INGREDIENT).rest_sec == RULES["whole_cut"].rest_sec
    assert with_rest_time(VALID_RECIPE, RULE_BY_INGREDIENT).rest_sec == RULES["poultry"].rest_sec


class DisobedientLLM(LLMProvider):
    """Giả lập model phớt lờ system prompt: hạ nhiệt độ xào gà xuống 50°C."""

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        return with_steps(PREP, STIR_FRY_CHICKEN.model_copy(update={"temperature_c": 50}), PLATE).model_dump_json()


def test_validation_blocks_disobedient_llm_output_end_to_end() -> None:
    raw = asyncio.run(DisobedientLLM().generate_json("system", "user", AdaptedRecipe))
    recipe = AdaptedRecipe.model_validate_json(raw)

    assert recipe.steps[1].temperature_c == 50  # output đúng schema — strict mode không chặn được lỗi này
    reason = validate_adapted_recipe(recipe, CONTEXT)
    assert reason is not None and f"≥{RULES['poultry'].min_temp_c}°C" in reason


@pytest.mark.skipif(not os.getenv("SUPABASE_SECRET_KEY"), reason="cần SUPABASE_SECRET_KEY để đọc bảng thật")
def test_threshold_fixture_matches_real_food_safety_table() -> None:
    from scripts.supabase_admin import create_admin_client

    rows = create_admin_client().table("food_safety").select("category,min_temp_c,min_duration_sec,rest_sec").execute()
    assert {row["category"]: safety_rule_from_row(row) for row in rows.data} == RULES
