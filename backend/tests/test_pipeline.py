"""Pipeline: nhánh adapted / original, fallback LLM, dinh dưỡng từ DB, lỗi vision. Không gọi mạng (provider giả)."""

import asyncio
import dataclasses
import logging

import pytest
from pydantic import BaseModel

from app.services.ingredient_matching import CatalogIngredient
from app.services.ingredient_normalizer import MatchStatus
from app.services.llm.fallback import FallbackLLM
from app.services.llm.provider import LLMProvider, LLMUnavailableError
from app.services.llm.recipe_adaptation import AdaptedIngredient, AdaptedRecipe, AdaptedStep
from app.services.nutrition import Nutrition
from app.services import pipeline
from app.services.pipeline import (
    UNMAPPED_INGREDIENTS_WARNING,
    NoUsableIngredientsError,
    SuggestRequest,
    adapt_or_fallback,
    recognize_ingredients,
    suggest_recipes,
)
from app.services.recipe_repository import OriginalRecipe, RecipeIngredientInfo, SearchHit
from app.services.validation import safety_rule_from_row
from app.services.vision.provider import Detected, VisionProvider, VisionUnavailableError
from scripts.seed_food_safety import FOOD_SAFETY_THRESHOLDS

POULTRY = safety_rule_from_row(next(row for row in FOOD_SAFETY_THRESHOLDS if row["category"] == "poultry"))
CHICKEN_ID, FISH_SAUCE_ID = 93, 157
CHICKEN_FACTS = Nutrition(kcal=120, protein_g=22.5, carb_g=0, fat_g=2.6)
ORIGINAL_SERVINGS, CHICKEN_GRAMS = 2, 300

ORIGINAL = OriginalRecipe(
    hit=SearchHit(recipe_id=7, title="Gà kho", servings=ORIGINAL_SERVINGS, score=0.8),
    ingredients=[
        RecipeIngredientInfo(CHICKEN_ID, "Ức gà", CHICKEN_GRAMS, "g", POULTRY, frozenset(), CHICKEN_FACTS),
        RecipeIngredientInfo(FISH_SAUCE_ID, "Nước mắm", None, None, None, frozenset({"fish"}), None),
    ],
    steps=[AdaptedStep(step_no=1, action="kho gà", temperature_c=None, duration_sec=None)],
)
REQUEST = SuggestRequest(ingredient_ids=[CHICKEN_ID, FISH_SAUCE_ID], diet_type="omnivore", allergens=[], servings=4)
# Dinh dưỡng/suất đúng: 300g gà × 120 kcal/100g ÷ 2 suất gốc = 180 kcal
EXPECTED_KCAL_PER_SERVING = CHICKEN_GRAMS * CHICKEN_FACTS.kcal / 100 / ORIGINAL_SERVINGS


def adapted_json(temperature_c: float, chicken_grams: float = 600) -> str:
    """Output LLM giả đúng schema."""
    return AdaptedRecipe(
        title="Gà kho tộ", servings=4,
        ingredients=[AdaptedIngredient(ingredient_id=CHICKEN_ID, amount=chicken_grams, unit="g")],
        steps=[AdaptedStep(step_no=1, action="Kho gà đến chín.", temperature_c=temperature_c, duration_sec=900)],
    ).model_dump_json()


class ScriptedLLM(LLMProvider):
    """Trả chuỗi cho sẵn, hoặc ném lỗi cho sẵn; đếm số lần được gọi."""

    def __init__(self, output: str | Exception) -> None:
        self.output, self.calls = output, 0

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def run_adapt(llm: LLMProvider):
    return asyncio.run(adapt_or_fallback(ORIGINAL, REQUEST, llm))


def test_valid_llm_output_is_adapted_and_nutrition_ignores_llm_amounts() -> None:
    result = run_adapt(ScriptedLLM(adapted_json(temperature_c=80, chicken_grams=5000)))  # LLM ghi sai lượng gà

    assert result.source == "adapted" and result.servings == 4
    assert [item.name for item in result.ingredients] == ["Ức gà"]  # tên lấy từ DB
    assert result.nutrition_per_serving.kcal == EXPECTED_KCAL_PER_SERVING  # không theo 5000g của LLM
    assert result.rest_sec == POULTRY.rest_sec


def test_validation_fail_returns_original_and_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = run_adapt(ScriptedLLM(adapted_json(temperature_c=50)))

    assert result.source == "original" and result.title == "Gà kho"
    assert "Validation fail recipe 7" in caplog.text and "poultry" in caplog.text
    assert result.nutrition_per_serving.kcal == EXPECTED_KCAL_PER_SERVING


def test_output_not_matching_schema_returns_original_and_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = run_adapt(ScriptedLLM('{"title": "thiếu field"}'))

    assert result.source == "original"
    assert "Validation fail recipe 7" in caplog.text


def test_all_llms_unavailable_returns_original() -> None:
    chain = FallbackLLM([ScriptedLLM(LLMUnavailableError("429")), ScriptedLLM(LLMUnavailableError("timeout"))])
    assert run_adapt(chain).source == "original"


def test_other_llm_error_returns_original() -> None:
    assert run_adapt(ScriptedLLM(ValueError("finish_reason=length"))).source == "original"


def test_fallback_moves_to_next_provider_only_on_unavailable() -> None:
    rate_limited, backup = ScriptedLLM(LLMUnavailableError("429")), ScriptedLLM(adapted_json(temperature_c=80))
    assert run_adapt(FallbackLLM([rate_limited, backup])).source == "adapted"
    assert (rate_limited.calls, backup.calls) == (1, 1)

    broken, unused = ScriptedLLM(ValueError("lỗi khác")), ScriptedLLM(adapted_json(temperature_c=80))
    assert run_adapt(FallbackLLM([broken, unused])).source == "original"
    assert unused.calls == 0  # lỗi không phải 429/timeout → không thử tiếp


def test_suggest_without_ingredients_stops_before_search() -> None:
    empty = SuggestRequest(ingredient_ids=[], diet_type="omnivore", allergens=[])
    with pytest.raises(NoUsableIngredientsError):
        asyncio.run(suggest_recipes(empty, client=None, embedder=None, llm=ScriptedLLM("{}")))


FOODCOM_ORIGINAL = dataclasses.replace(ORIGINAL, hit=dataclasses.replace(
    ORIGINAL.hit, source_url="https://www.food.com/recipe/1", raw_ingredient_names=("kaffir lime leaf",),
))


def test_unmapped_ingredients_warn_but_do_not_block() -> None:
    adapted = asyncio.run(adapt_or_fallback(FOODCOM_ORIGINAL, REQUEST, ScriptedLLM(adapted_json(temperature_c=80))))
    original = asyncio.run(adapt_or_fallback(FOODCOM_ORIGINAL, REQUEST, ScriptedLLM(ValueError("lỗi"))))

    for result in (adapted, original):
        assert result.has_unmapped_ingredients
        assert result.model_dump()["unmapped_ingredients_warning"] == UNMAPPED_INGREDIENTS_WARNING
    assert run_adapt(ScriptedLLM(ValueError("lỗi"))).model_dump()["unmapped_ingredients_warning"] is None


def test_pantry_basics_alone_do_not_trigger_unmapped_warning() -> None:
    only_basics = dataclasses.replace(ORIGINAL.hit, raw_ingredient_names=("water", "hạt nêm aji ngon heo", "tiêu xay"))
    assert not only_basics.has_unmapped_ingredients
    assert dataclasses.replace(only_basics, raw_ingredient_names=("tiêu", "nấm mèo")).has_unmapped_ingredients


def test_foodcom_original_is_labelled_english_but_adapted_is_vietnamese() -> None:
    assert asyncio.run(adapt_or_fallback(FOODCOM_ORIGINAL, REQUEST, ScriptedLLM(ValueError("lỗi")))).language == "en"
    assert asyncio.run(
        adapt_or_fallback(FOODCOM_ORIGINAL, REQUEST, ScriptedLLM(adapted_json(temperature_c=80)))
    ).language == "vi"
    assert run_adapt(ScriptedLLM(ValueError("lỗi"))).language == "vi"  # ViFoodRec không có source_url


class ConcurrencyProbeLLM(LLMProvider):
    """Ghi lại số lượt gọi đang chạy cùng lúc nhiều nhất."""

    def __init__(self) -> None:
        self.running = self.max_running = 0

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        await asyncio.sleep(0.01)
        self.running -= 1
        return adapted_json(temperature_c=80)


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def test_suggest_calls_llm_for_all_recipes_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    recipe_count = 5

    async def fake_catalog(client):
        return CATALOG

    async def fake_search(*args):
        return [ORIGINAL.hit] * recipe_count

    async def fake_load(client, hits):
        return [ORIGINAL] * len(hits)

    monkeypatch.setattr(pipeline, "load_ingredient_catalog", fake_catalog)
    monkeypatch.setattr(pipeline, "search_recipes", fake_search)
    monkeypatch.setattr(pipeline, "load_original_recipes", fake_load)
    llm = ConcurrencyProbeLLM()

    results = asyncio.run(suggest_recipes(REQUEST, client=None, embedder=FakeEmbedder(), llm=llm))

    assert len(results) == recipe_count and llm.max_running == recipe_count


class ScriptedVision(VisionProvider):
    def __init__(self, output: Detected | Exception) -> None:
        self.output = output

    async def detect_ingredients(self, image: bytes, mime_type: str) -> Detected:
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


CATALOG = [CatalogIngredient(id=CHICKEN_ID, name_vi="Ức gà", name_en="Chicken breast"),
           CatalogIngredient(id=16, name_vi="Tỏi", name_en="Garlic")]


def run_recognize(vision: VisionProvider):
    return asyncio.run(recognize_ingredients(b"img", "image/jpeg", vision, CATALOG))


def test_recognize_keeps_vision_uncertain_for_user_to_confirm() -> None:
    result = run_recognize(ScriptedVision(Detected(ingredients=["ức gà", "sô cô la"], uncertain=["tỏi"])))

    assert result.accepted_ids == [CHICKEN_ID]
    assert [(m.ingredient_id, m.status) for m in result.uncertain] == [(16, MatchStatus.UNCERTAIN)]
    assert result.unmatched_names == ["sô cô la"]


def test_recognize_distinguishes_vision_error_from_no_food() -> None:
    with pytest.raises(VisionUnavailableError):
        run_recognize(ScriptedVision(VisionUnavailableError("timeout")))
    with pytest.raises(NoUsableIngredientsError):
        run_recognize(ScriptedVision(Detected(ingredients=[], uncertain=[])))
