"""Pipeline gợi ý công thức (feature-spec mục 4): vision → normalize → search_recipes → LLM adapt → validate.

Hai bước tách theo 2 endpoint vì giữa chúng user xác nhận nguyên liệu (bước [5]):
- recognize_ingredients: ảnh → nguyên liệu đã map vào bảng ingredients
- suggest_recipes: nguyên liệu đã xác nhận + diet/dị ứng → công thức (adapted hoặc original)
"""

import asyncio
import dataclasses
import json
import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError, computed_field
from supabase import AsyncClient

from app.services.embedding.provider import EmbeddingProvider
from app.services.ingredient_matching import CatalogIngredient
from app.services.ingredient_normalizer import (
    IngredientMatch,
    IngredientNormalizer,
    MatchStatus,
    accepted_ingredient_ids,
    load_ingredient_catalog,
)
from app.services.llm.provider import LLMProvider, LLMUnavailableError
from app.services.llm.recipe_adaptation import ADAPT_RECIPE_SYSTEM_PROMPT, AdaptedRecipe, AdaptedStep
from app.services.nutrition import Nutrition, nutrition_per_serving
from app.services.recipe_repository import OriginalRecipe, RecipeLanguage, load_original_recipes, search_recipes
from app.services.validation import (
    SafetyRule,
    ValidationContext,
    max_rest_sec,
    validate_adapted_recipe,
    with_rest_time,
)
from app.services.vision.provider import VisionProvider, VisionUnavailableError

logger = logging.getLogger(__name__)

RecipeSource = Literal["adapted", "original"]
UNMAPPED_INGREDIENTS_WARNING = (
    "Một số nguyên liệu trong công thức gốc chưa được hệ thống nhận diện đầy đủ — kiểm tra chín kỹ trước khi ăn"
)


class NoUsableIngredientsError(Exception):
    """Không có nguyên liệu nào dùng được → dừng, không search, không gọi LLM (lớp validation 1)."""


@dataclass(frozen=True)
class RecognizedIngredients:
    """Kết quả bước [3]–[4], client hiển thị cho user xác nhận."""

    accepted_ids: list[int]
    uncertain: list[IngredientMatch]  # vision chưa chắc hoặc map mờ → hỏi lại user
    unmatched_names: list[str]  # không có trong bảng ingredients


@dataclass(frozen=True)
class SuggestRequest:
    """Body /recipes/suggest; allergens là slug (feature-spec mục 6)."""

    ingredient_ids: list[int]
    diet_type: str
    allergens: list[str]
    servings: int | None = None  # None = giữ khẩu phần công thức gốc


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
    language: RecipeLanguage = "vi"  # "en" = bản gốc Food.com, client gắn nhãn thay vì dịch

    @computed_field
    @property
    def unmapped_ingredients_warning(self) -> str | None:
        """Dòng cảnh báo client hiển thị kèm công thức (cùng kiểu disclaimer ảnh AI)."""
        return UNMAPPED_INGREDIENTS_WARNING if self.has_unmapped_ingredients else None


async def recognize_ingredients(
    image: bytes, mime_type: str, vision: VisionProvider, catalog: list[CatalogIngredient],
) -> RecognizedIngredients:
    """Ảnh → nguyên liệu đã map; VisionUnavailableError nếu vision lỗi, NoUsableIngredientsError nếu không có gì."""
    try:
        detected = await vision.detect_ingredients(image, mime_type)
    except VisionUnavailableError:
        logger.exception("Vision không nhận diện được ảnh")
        raise
    if not detected.ingredients and not detected.uncertain:
        raise NoUsableIngredientsError("Ảnh không có thực phẩm")
    normalizer = IngredientNormalizer(catalog)
    matches = normalizer.normalize(detected.ingredients) + [
        demote_to_uncertain(match) for match in normalizer.normalize(detected.uncertain)
    ]
    accepted = accepted_ingredient_ids(matches)
    uncertain = [match for match in matches if match.status is MatchStatus.UNCERTAIN]
    if not accepted and not uncertain:
        raise NoUsableIngredientsError("Không nguyên liệu nào khớp với danh mục")
    rejected = [match.raw_name for match in matches if match.status is MatchStatus.REJECTED]
    return RecognizedIngredients(accepted_ids=accepted, uncertain=uncertain, unmatched_names=rejected)


def demote_to_uncertain(match: IngredientMatch) -> IngredientMatch:
    """Vision đã nói "không chắc" → dù map khớp cũng không tự nhận, để user xác nhận."""
    if match.status is MatchStatus.ACCEPTED:
        return dataclasses.replace(match, status=MatchStatus.UNCERTAIN)
    return match


async def suggest_recipes(
    request: SuggestRequest, client: AsyncClient, embedder: EmbeddingProvider, llm: LLMProvider,
) -> list[SuggestedRecipe]:
    """Nguyên liệu đã xác nhận → tối đa 5 công thức, mỗi món adapted nếu LLM + validation pass, ngược lại original."""
    if not request.ingredient_ids:
        raise NoUsableIngredientsError("Chưa có nguyên liệu nào được xác nhận")
    catalog = await load_ingredient_catalog(client)
    [query_embedding] = await embedder.embed([build_query_text(request.ingredient_ids, catalog)])
    hits = await search_recipes(
        client, query_embedding, request.diet_type, request.allergens, request.ingredient_ids,
    )
    originals = await load_original_recipes(client, hits) if hits else []
    return list(await asyncio.gather(*(adapt_or_fallback(original, request, llm) for original in originals)))


def build_query_text(ingredient_ids: list[int], catalog: list[CatalogIngredient]) -> str:
    """Cùng dạng phần nguyên liệu của embed_text lúc seed (tên VI + EN) để vector cùng không gian."""
    by_id = {ingredient.id: ingredient for ingredient in catalog}
    names = [name for i in ingredient_ids if i in by_id for name in (by_id[i].name_vi, by_id[i].name_en) if name]
    return f"Nguyên liệu: {', '.join(dict.fromkeys(names))}"


async def adapt_or_fallback(original: OriginalRecipe, request: SuggestRequest, llm: LLMProvider) -> SuggestedRecipe:
    """LLM chỉnh công thức → validate; lỗi LLM hoặc validation fail → trả công thức gốc."""
    recipe_id = original.hit.recipe_id
    try:
        user_prompt = build_adapt_user_prompt(original, request)
        raw = await llm.generate_json(ADAPT_RECIPE_SYSTEM_PROMPT, user_prompt, AdaptedRecipe)
    except LLMUnavailableError as error:
        logger.warning("Recipe %d: mọi LLM đều 429/timeout, trả công thức gốc (%s)", recipe_id, error)
        return original_result(original)
    except Exception:
        logger.exception("Recipe %d: LLM lỗi, trả công thức gốc", recipe_id)
        return original_result(original)
    try:
        adapted = AdaptedRecipe.model_validate_json(raw)
    except ValidationError as error:
        logger.warning("Validation fail recipe %d: output LLM sai schema (%s) | output: %s", recipe_id, error, raw)
        return original_result(original)
    reason = validate_adapted_recipe(adapted, validation_context(original, request.allergens))
    if reason is not None:
        logger.warning("Validation fail recipe %d: %s | output: %s", recipe_id, reason, raw)
        return original_result(original)
    return adapted_result(original, with_rest_time(adapted, rules_by_ingredient(original)))


def build_adapt_user_prompt(original: OriginalRecipe, request: SuggestRequest) -> str:
    """User prompt JSON: công thức gốc + nguyên liệu user có + khẩu phần mong muốn."""
    return json.dumps({
        "khẩu_phần_mong_muốn": request.servings or original.hit.servings,
        "ingredient_id_người_dùng_có": request.ingredient_ids,
        "công_thức_gốc": {
            "title": original.hit.title,
            "servings": original.hit.servings,
            "ingredients": [
                {"ingredient_id": item.ingredient_id, "name": item.name_vi, "amount": item.amount, "unit": item.unit}
                for item in original.ingredients
            ],
            "steps": [step.model_dump() for step in original.steps],
        },
    }, ensure_ascii=False)


def rules_by_ingredient(original: OriginalRecipe) -> dict[int, SafetyRule]:
    """ingredient_id → SafetyRule của các nguyên liệu cần nấu chín trong công thức gốc."""
    return {item.ingredient_id: item.safety_rule for item in original.ingredients if item.safety_rule}


def validation_context(original: OriginalRecipe, user_allergens: list[str]) -> ValidationContext:
    """Whitelist + dị ứng + ngưỡng an toàn, đều tra từ DB theo công thức gốc."""
    return ValidationContext(
        allowed_ingredient_ids=frozenset(item.ingredient_id for item in original.ingredients),
        user_allergens=frozenset(user_allergens),
        allergens_by_ingredient={item.ingredient_id: item.allergens for item in original.ingredients},
        safety_rule_by_ingredient=rules_by_ingredient(original),
    )


def nutrition_from_original(original: OriginalRecipe, kept_ids: set[int]) -> Nutrition | None:
    """Dinh dưỡng/suất tính từ gram + nutrition_facts của công thức GỐC, chỉ các nguyên liệu còn giữ.

    Không dùng amount của LLM: chia theo servings gốc cho ra số/suất — không đổi khi LLM nhân khẩu phần.
    ponytail: nguyên liệu gốc không ghi gram (toàn bộ Food.com) bị bỏ qua; không có gram nào → None.
    """
    grams = {
        item.ingredient_id: item.grams for item in original.ingredients if item.ingredient_id in kept_ids and item.grams
    }
    if not grams:
        return None
    facts = {item.ingredient_id: item.facts_per_100g for item in original.ingredients if item.facts_per_100g}
    return nutrition_per_serving(grams, facts, original.hit.servings)


def original_result(original: OriginalRecipe) -> SuggestedRecipe:
    """Công thức gốc đã kiểm duyệt, không qua LLM."""
    ingredient_ids = [item.ingredient_id for item in original.ingredients]
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
        language=original.hit.original_language,
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
    )
