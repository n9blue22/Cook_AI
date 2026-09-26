"""Lớp validation 3 (feature-spec mục 5): kiểm tra công thức LLM trả về bằng code, không hỏi lại LLM.

Fail bất kỳ kiểm tra nào → pipeline trả công thức gốc đã kiểm duyệt (fallback), không cố sửa bản lỗi.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.services.llm.recipe_adaptation import AdaptedRecipe, AdaptedStep


@dataclass(frozen=True)
class SafetyRule:
    """Một dòng bảng food_safety: ngưỡng nấu chín tối thiểu + thời gian nghỉ sau khi tắt bếp."""

    category: str
    min_temp_c: float
    min_duration_sec: int  # điều kiện validate bước nấu
    rest_sec: int  # chỉ để hiển thị, KHÔNG validate (không phải một bước nấu)


def safety_rule_from_row(row: Mapping[str, Any]) -> SafetyRule:
    """Dòng food_safety (từ DB hoặc seed) → SafetyRule."""
    return SafetyRule(
        category=row["category"],
        min_temp_c=float(row["min_temp_c"]),
        min_duration_sec=int(row["min_duration_sec"]),
        rest_sec=int(row["rest_sec"]),
    )


@dataclass(frozen=True)
class ValidationContext:
    """Dữ liệu tra từ DB cho một lần validate; nguyên liệu không có trong map = không dị ứng / không cần nấu chín."""

    allowed_ingredient_ids: frozenset[int]  # nguyên liệu của công thức gốc (whitelist)
    user_allergens: frozenset[str]  # allergens.slug user khai
    allergens_by_ingredient: Mapping[int, frozenset[str]]
    safety_rule_by_ingredient: Mapping[int, SafetyRule]


def validate_adapted_recipe(recipe: AdaptedRecipe, context: ValidationContext) -> str | None:
    """None nếu công thức an toàn để trả user; ngược lại là lý do fail đầu tiên."""
    if not recipe.steps:
        return "Công thức không có bước nào"
    if recipe.servings < 1:
        return f"Khẩu phần không hợp lệ: {recipe.servings}"
    non_positive = [item.ingredient_id for item in recipe.ingredients if item.amount is not None and item.amount <= 0]
    if non_positive:
        return f"Lượng nguyên liệu ≤ 0: {non_positive}"
    ingredient_ids = [item.ingredient_id for item in recipe.ingredients]
    return (
        find_foreign_ingredient(ingredient_ids, context.allowed_ingredient_ids)
        or find_user_allergen(ingredient_ids, context)
        or check_cooking_safety(ingredient_ids, recipe.steps, context.safety_rule_by_ingredient)
    )


def find_foreign_ingredient(ingredient_ids: list[int], allowed_ids: frozenset[int]) -> str | None:
    """Kiểm tra 1: LLM không được thêm nguyên liệu ngoài công thức gốc."""
    foreign = sorted(set(ingredient_ids) - allowed_ids)
    return f"Nguyên liệu không có trong công thức gốc: {foreign}" if foreign else None


def find_user_allergen(ingredient_ids: list[int], context: ValidationContext) -> str | None:
    """Kiểm tra 2: không nguyên liệu nào thuộc allergen user đã khai."""
    for ingredient_id in ingredient_ids:
        hits = context.allergens_by_ingredient.get(ingredient_id, frozenset()) & context.user_allergens
        if hits:
            return f"Nguyên liệu {ingredient_id} chứa allergen user đã khai: {sorted(hits)}"
    return None


def is_cooking_step(step: AdaptedStep) -> bool:
    """Bước có cả nhiệt độ lẫn thời gian = bước nấu (sơ chế/bày đĩa để null)."""
    return step.temperature_c is not None and step.duration_sec is not None


def check_cooking_safety(
    ingredient_ids: list[int], steps: list[AdaptedStep], rule_by_ingredient: Mapping[int, SafetyRule],
) -> str | None:
    """Kiểm tra 3 + 4: có thịt/cá/trứng thì phải còn bước nấu, và bước nấu đạt ngưỡng food_safety của từng nhóm.

    ponytail: bước không gắn với nguyên liệu nên chỉ đòi "có ít nhất một bước đạt ngưỡng" cho mỗi nhóm —
    một bước nóng khác (vd luộc rau 100°C) có thể che bước thịt bị hạ nhiệt.
    Cần gắn ingredient_id vào step nếu muốn chặt hơn.

    Ngưỡng 15 giây theo FDA Food Code (min_duration_sec) gần như không có tác dụng lọc thực tế, vì duration_sec
    đo cả bước nấu chứ không phải thời gian giữ đúng ở nhiệt độ đích — ngưỡng này tồn tại để đúng chuẩn pháp lý,
    KHÔNG phải cơ chế chặn chính. Cơ chế chặn thật sự nằm ở min_temp_c (74°C gia cầm, 71°C thịt xay...) —
    đây mới là điều kiện có khả năng fail thật khi model hạ nhiệt độ sai.
    """
    rules = {rule_by_ingredient[i] for i in ingredient_ids if i in rule_by_ingredient}
    if not rules:
        return None
    cooking_steps = [step for step in steps if is_cooking_step(step)]
    if not cooking_steps:
        return f"Có nguyên liệu cần nấu chín ({sorted(rule.category for rule in rules)}) nhưng không còn bước nấu"
    for rule in sorted(rules, key=lambda rule: rule.category):
        if not any(
            step.temperature_c >= rule.min_temp_c and step.duration_sec >= rule.min_duration_sec
            for step in cooking_steps
        ):
            return (
                f"Không bước nào đạt ngưỡng an toàn '{rule.category}' "
                f"(≥{rule.min_temp_c}°C, ≥{rule.min_duration_sec}s)"
            )
    return None


def max_rest_sec(ingredient_ids: list[int], rule_by_ingredient: Mapping[int, SafetyRule]) -> int:
    """Thời gian nghỉ dài nhất trong các nhóm nguyên liệu (0 = không cần nghỉ)."""
    return max((rule_by_ingredient[i].rest_sec for i in ingredient_ids if i in rule_by_ingredient), default=0)


def with_rest_time(recipe: AdaptedRecipe, rule_by_ingredient: Mapping[int, SafetyRule]) -> AdaptedRecipe:
    """Gắn rest_sec từ food_safety vào công thức — gọi sau khi validate pass."""
    ingredient_ids = [item.ingredient_id for item in recipe.ingredients]
    return recipe.model_copy(update={"rest_sec": max_rest_sec(ingredient_ids, rule_by_ingredient)})
