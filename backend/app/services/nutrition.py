"""Tính dinh dưỡng công thức từ nutrition_facts (không bao giờ để LLM tự sinh số)."""

from dataclasses import dataclass

GRAMS_PER_NUTRITION_UNIT = 100  # nutrition_facts tính trên 100g


@dataclass(frozen=True)
class Nutrition:
    """kcal và macro (gram) — dùng cho cả giá trị /100g lẫn /khẩu phần."""

    kcal: float
    protein_g: float
    carb_g: float
    fat_g: float


def nutrition_per_serving(
    grams_by_ingredient: dict[int, float], facts_per_100g: dict[int, Nutrition], servings: int,
) -> Nutrition:
    """Cộng dinh dưỡng theo gram từng nguyên liệu rồi chia khẩu phần; nguyên liệu thiếu facts bị bỏ qua."""
    totals = [0.0, 0.0, 0.0, 0.0]
    for ingredient_id, grams in grams_by_ingredient.items():
        facts = facts_per_100g.get(ingredient_id)
        if facts is None:
            continue
        ratio = grams / GRAMS_PER_NUTRITION_UNIT
        for index, value in enumerate((facts.kcal, facts.protein_g, facts.carb_g, facts.fat_g)):
            totals[index] += value * ratio
    kcal, protein, carb, fat = (round(total / servings, 1) for total in totals)
    return Nutrition(kcal=kcal, protein_g=protein, carb_g=carb, fat_g=fat)
