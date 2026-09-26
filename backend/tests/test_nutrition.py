"""Test tính dinh dưỡng mỗi khẩu phần từ nutrition_facts."""

from app.services.nutrition import Nutrition, nutrition_per_serving

RICE_ID = 1
PORK_ID = 2
FACTS = {
    RICE_ID: Nutrition(kcal=130, protein_g=2.7, carb_g=28, fat_g=0.3),
    PORK_ID: Nutrition(kcal=240, protein_g=27, carb_g=0, fat_g=14),
}


def test_sums_by_grams_and_divides_by_servings() -> None:
    result = nutrition_per_serving({RICE_ID: 200, PORK_ID: 100}, FACTS, servings=2)
    assert result == Nutrition(kcal=250, protein_g=16.2, carb_g=28, fat_g=7.3)


def test_doubling_servings_and_amounts_keeps_per_serving_and_doubles_total() -> None:
    for_two = nutrition_per_serving({RICE_ID: 200}, FACTS, servings=2)
    for_four = nutrition_per_serving({RICE_ID: 400}, FACTS, servings=4)
    assert for_four == for_two
    assert for_four.kcal * 4 == 2 * (for_two.kcal * 2)


def test_ingredient_without_facts_is_ignored() -> None:
    assert nutrition_per_serving({999: 500}, FACTS, servings=1) == Nutrition(0, 0, 0, 0)
