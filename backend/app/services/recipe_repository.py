"""Đọc dữ liệu pipeline gợi ý công thức từ Supabase (publishable key — search_recipes là SECURITY DEFINER)."""

from dataclasses import dataclass
from typing import Any, Literal

from supabase import AsyncClient

from app.services.ingredient_normalizer import is_pantry_basic
from app.services.llm.recipe_adaptation import AdaptedStep
from app.services.nutrition import Nutrition
from app.services.validation import SafetyRule, safety_rule_from_row

GRAM_UNIT = "g"
RECIPE_INGREDIENT_COLUMNS = (
    "recipe_id,ingredient_id,amount,unit,"
    "ingredients(name_vi,food_safety(category,min_temp_c,min_duration_sec,rest_sec),"
    "ingredient_allergens(allergens(slug)),nutrition_facts(kcal_100g,protein_g,carb_g,fat_g))"
)
RECIPE_STEP_COLUMNS = "recipe_id,step_no,instruction,min_temp_c,min_duration_sec"

RecipeLanguage = Literal["vi", "en"]


@dataclass(frozen=True)
class SearchHit:
    """Một dòng search_recipes."""

    recipe_id: int
    title: str
    servings: int
    score: float
    source_url: str | None = None  # chỉ Food.com có; ViFoodRec (tiếng Việt) để trống
    raw_ingredient_names: tuple[str, ...] = ()  # tên nguyên liệu gốc chưa map được về bảng ingredients

    @property
    def has_unmapped_ingredients(self) -> bool:
        """Còn nguyên liệu chưa nhận diện (ngoài validation/food_safety) — nước, muối, tiêu, hạt nêm… không tính."""
        return any(not is_pantry_basic(name) for name in self.raw_ingredient_names)

    @property
    def original_language(self) -> RecipeLanguage:
        """Ngôn ngữ của title/bước gốc: Food.com (có source_url) là tiếng Anh."""
        return "en" if self.source_url else "vi"


@dataclass(frozen=True)
class RecipeIngredientInfo:
    """Nguyên liệu của công thức gốc kèm mọi thứ validation + dinh dưỡng cần (tra từ DB, không từ LLM)."""

    ingredient_id: int
    name_vi: str
    amount: float | None
    unit: str | None
    safety_rule: SafetyRule | None
    allergens: frozenset[str]
    facts_per_100g: Nutrition | None

    @property
    def grams(self) -> float | None:
        """Khối lượng gram nếu công thức gốc ghi theo g (Food.com không có lượng → None)."""
        return self.amount if self.unit == GRAM_UNIT and self.amount else None


@dataclass(frozen=True)
class OriginalRecipe:
    """Công thức gốc đã kiểm duyệt — nguồn cho LLM và là bản fallback."""

    hit: SearchHit
    ingredients: list[RecipeIngredientInfo]
    steps: list[AdaptedStep]


async def search_recipes(
    client: AsyncClient, query_embedding: list[float], diet: str, allergens: list[str], ingredient_ids: list[int],
) -> list[SearchHit]:
    """Gọi RPC search_recipes (lọc cứng diet + dị ứng trong SQL)."""
    params = {
        "query_embedding": query_embedding, "p_diet": diet, "p_allergens": allergens,
        "p_ingredient_ids": ingredient_ids,
    }
    rows = (await client.rpc("search_recipes", params).execute()).data
    return [
        SearchHit(
            row["recipe_id"], row["title"], row["servings"], row["score"],
            row["source_url"], tuple(row["raw_ingredient_names"]),
        )
        for row in rows
    ]


async def load_original_recipes(client: AsyncClient, hits: list[SearchHit]) -> list[OriginalRecipe]:
    """Nguyên liệu + bước của các công thức tìm được, 2 request cho cả danh sách, giữ thứ tự hits."""
    recipe_ids = [hit.recipe_id for hit in hits]
    ingredient_rows = (
        await client.table("recipe_ingredients").select(RECIPE_INGREDIENT_COLUMNS)
        .in_("recipe_id", recipe_ids).execute()
    ).data
    step_rows = (
        await client.table("recipe_steps").select(RECIPE_STEP_COLUMNS).in_("recipe_id", recipe_ids)
        .order("step_no").execute()
    ).data
    return [
        OriginalRecipe(
            hit=hit,
            ingredients=[
                ingredient_info_from_row(row) for row in ingredient_rows if row["recipe_id"] == hit.recipe_id
            ],
            steps=[step_from_row(row) for row in step_rows if row["recipe_id"] == hit.recipe_id],
        )
        for hit in hits
    ]


def ingredient_info_from_row(row: dict[str, Any]) -> RecipeIngredientInfo:
    """1 dòng recipe_ingredients (embed ingredients → food_safety, allergens, nutrition_facts) → info."""
    ingredient = row["ingredients"]
    facts = ingredient["nutrition_facts"]
    return RecipeIngredientInfo(
        ingredient_id=row["ingredient_id"],
        name_vi=ingredient["name_vi"],
        amount=row["amount"],
        unit=row["unit"],
        safety_rule=safety_rule_from_row(ingredient["food_safety"]) if ingredient["food_safety"] else None,
        allergens=frozenset(link["allergens"]["slug"] for link in ingredient["ingredient_allergens"]),
        facts_per_100g=Nutrition(
            kcal=facts["kcal_100g"], protein_g=facts["protein_g"], carb_g=facts["carb_g"], fat_g=facts["fat_g"],
        ) if facts else None,
    )


def step_from_row(row: dict[str, Any]) -> AdaptedStep:
    """1 dòng recipe_steps → cùng dạng bước với output LLM."""
    return AdaptedStep(
        step_no=row["step_no"], action=row["instruction"],
        temperature_c=row["min_temp_c"], duration_sec=row["min_duration_sec"],
    )
