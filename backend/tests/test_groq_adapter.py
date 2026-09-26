"""Test GroqAdapter: helper schema strict (offline) + gọi Groq thật (cần GROQ_API_KEY, không có thì skip)."""

import asyncio
import json
import os
from typing import Any

import pytest

from app.services.llm.groq_adapter import GroqAdapter  # import này nạp backend/.env
from app.services.llm.strict_schema import to_strict_json_schema
from app.services.llm.recipe_adaptation import ADAPT_RECIPE_SYSTEM_PROMPT, AdaptedRecipe
from scripts.seed_food_safety import FOOD_SAFETY_THRESHOLDS

CHICKEN_BREAST_ID = 93
CILANTRO_ID = 51  # rau mùi — nguyên liệu phụ user không có
CHICKEN_SAFE_TEMP_C = next(row["min_temp_c"] for row in FOOD_SAFETY_THRESHOLDS if row["category"] == "poultry")
ORIGINAL_CHICKEN_COOK_SEC = 480

ORIGINAL_RECIPE = {
    "title": "Gà xào sả ớt",
    "servings": 2,
    "ingredients": [
        {"ingredient_id": CHICKEN_BREAST_ID, "name": "Ức gà", "amount": 300, "unit": "g"},
        {"ingredient_id": 18, "name": "Sả", "amount": 3, "unit": "cây"},
        {"ingredient_id": 19, "name": "Ớt", "amount": 2, "unit": "quả"},
        {"ingredient_id": 16, "name": "Tỏi", "amount": 3, "unit": "tép"},
        {"ingredient_id": 157, "name": "Nước mắm", "amount": 2, "unit": "muỗng canh"},
        {"ingredient_id": 148, "name": "Dầu ăn", "amount": 2, "unit": "muỗng canh"},
        {"ingredient_id": CILANTRO_ID, "name": "Rau mùi", "amount": 10, "unit": "g"},
    ],
    "steps": [
        {"step_no": 1, "action": "Thái ức gà miếng vừa ăn, ướp nước mắm 15 phút. Băm sả, tỏi, ớt.",
         "temperature_c": None, "duration_sec": None},
        {"step_no": 2, "action": "Phi thơm sả tỏi ớt với dầu ăn, cho gà vào xào đến khi chín hẳn.",
         "temperature_c": 75, "duration_sec": ORIGINAL_CHICKEN_COOK_SEC},
        {"step_no": 3, "action": "Tắt bếp, rắc rau mùi, bày ra đĩa.", "temperature_c": None, "duration_sec": None},
    ],
}
USER_INGREDIENT_IDS = [CHICKEN_BREAST_ID, 18, 19, 16, 157, 148]  # không có rau mùi
TARGET_SERVINGS = 4


def object_nodes(node: Any) -> list[dict]:
    """Mọi node type=object trong schema (đệ quy)."""
    if isinstance(node, list):
        return [found for item in node for found in object_nodes(item)]
    if not isinstance(node, dict):
        return []
    children = [found for value in node.values() for found in object_nodes(value)]
    return ([node] if node.get("type") == "object" else []) + children


def test_strict_schema_closes_every_object_and_inlines_refs() -> None:
    schema = to_strict_json_schema(AdaptedRecipe)

    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    objects = object_nodes(schema)
    assert len(objects) == 3  # AdaptedRecipe, AdaptedIngredient, AdaptedStep
    for node in objects:
        assert node["additionalProperties"] is False
        assert node["required"] == list(node["properties"])


@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="cần GROQ_API_KEY để gọi Groq thật")
def test_adapts_servings_drops_missing_garnish_and_keeps_chicken_cooking() -> None:
    user_prompt = json.dumps({
        "khẩu_phần_mong_muốn": TARGET_SERVINGS,
        "ingredient_id_người_dùng_có": USER_INGREDIENT_IDS,
        "công_thức_gốc": ORIGINAL_RECIPE,
    }, ensure_ascii=False)
    raw = asyncio.run(GroqAdapter().generate_json(ADAPT_RECIPE_SYSTEM_PROMPT, user_prompt, AdaptedRecipe))
    print(raw)
    recipe = AdaptedRecipe.model_validate_json(raw)

    ingredient_ids = {item.ingredient_id for item in recipe.ingredients}
    assert ingredient_ids <= {item["ingredient_id"] for item in ORIGINAL_RECIPE["ingredients"]}  # không thêm mới
    assert CILANTRO_ID not in ingredient_ids
    assert recipe.servings == TARGET_SERVINGS
    chicken = next(item for item in recipe.ingredients if item.ingredient_id == CHICKEN_BREAST_ID)
    assert chicken.amount == 600  # 300g × 4/2
    assert any(
        (step.temperature_c or 0) >= CHICKEN_SAFE_TEMP_C and (step.duration_sec or 0) >= ORIGINAL_CHICKEN_COOK_SEC
        for step in recipe.steps
    )
    assert "calo" not in raw.lower()
