"""Pipeline: nhánh adapted / original, fallback LLM, dinh dưỡng từ DB, lỗi vision. Không gọi mạng (provider giả)."""

import asyncio
import dataclasses
import json
import logging

import pytest
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.services.ingredient_matching import CatalogIngredient
from app.services.ingredient_normalizer import IngredientCatalogCache, MatchStatus
from app.services.llm.fallback import FallbackLLM
from app.services.llm.provider import LLMProvider, LLMUnavailableError
from app.services.llm.recipe_adaptation import AdaptedIngredient, AdaptedRecipe, AdaptedStep
from app.services.nutrition import Nutrition
from app.services import ingredient_normalizer, pipeline
from app.services.pipeline import (
    NoUsableIngredientsError,
    SuggestRequest,
    adapt_or_fallback,
    recognize_ingredients,
    suggest_recipes,
)
from app.services.recipe_repository import OriginalRecipe, RecipeIngredientInfo, SearchHit
from app.services.rate_limit import RateLimitedError
from app.services.recipe_results import RAW_INGREDIENT_NOTE, UNMAPPED_INGREDIENTS_WARNING
from app.services.saved_recipe_service import SaveRecipeIn
from app.services.validation import safety_rule_from_row
from app.services.vision.provider import Detected, VisionProvider, VisionUnavailableError
from scripts.seed_food_safety import FOOD_SAFETY_THRESHOLDS

POULTRY = safety_rule_from_row(next(row for row in FOOD_SAFETY_THRESHOLDS if row["category"] == "poultry"))
CHICKEN_ID, FISH_SAUCE_ID = 93, 157
CHICKEN_FACTS = Nutrition(kcal=120, protein_g=22.5, carb_g=0, fat_g=2.6)
ORIGINAL_SERVINGS, CHICKEN_GRAMS, PREP_MINUTES = 2, 300, 25

ORIGINAL = OriginalRecipe(
    hit=SearchHit(recipe_id=7, title="Gà kho", servings=ORIGINAL_SERVINGS, score=0.8, prep_minutes=PREP_MINUTES),
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


def run_adapt(llm: LLMProvider, original: OriginalRecipe = ORIGINAL):
    return asyncio.run(adapt_or_fallback(original, REQUEST, llm))


CHICKEN_ONLY = dataclasses.replace(ORIGINAL, ingredients=ORIGINAL.ingredients[:1])


def test_valid_llm_output_is_adapted_and_nutrition_ignores_llm_amounts() -> None:
    # Gốc chỉ có gà: nước mắm (không ghi gram) sẽ được cộng lại và làm dinh dưỡng thành None — xem test dưới
    result = run_adapt(ScriptedLLM(adapted_json(temperature_c=80, chicken_grams=5000)), CHICKEN_ONLY)  # LLM ghi sai lượng gà

    assert result.source == "adapted" and result.servings == 4
    assert [item.name for item in result.ingredients] == ["Ức gà"]  # tên lấy từ DB
    assert result.nutrition_per_serving.kcal == EXPECTED_KCAL_PER_SERVING  # không theo 5000g của LLM
    assert result.rest_sec == POULTRY.rest_sec
    assert result.prep_minutes == PREP_MINUTES and not result.raw_ingredient_warning


def test_pantry_basic_dropped_by_llm_is_restored_and_nutrition_not_undercounted() -> None:
    result = run_adapt(ScriptedLLM(adapted_json(temperature_c=80)))  # LLM bỏ nước mắm dù gốc có

    assert result.source == "adapted"
    assert [item.name for item in result.ingredients] == ["Ức gà", "Nước mắm"]
    assert result.nutrition_per_serving is None  # nước mắm không ghi gram → không cộng thiếu (như bản gốc)


def test_validation_fail_returns_original_and_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = run_adapt(ScriptedLLM(adapted_json(temperature_c=50)))

    assert result.source == "original" and result.title == "Gà kho"
    assert "Validation fail recipe 7" in caplog.text and "poultry" in caplog.text
    assert result.prep_minutes == PREP_MINUTES
    # Nước mắm (bắt buộc) không ghi gram → không trả 180 kcal chỉ tính từ gà như thể đủ.
    assert result.nutrition_per_serving is None and result.model_dump()["nutrition_available"] is False
    # Bản gốc "kho gà" không ghi nhiệt độ → chưa biết, không kết luận "nguyên liệu sống".
    assert not result.raw_ingredient_warning and result.model_dump()["raw_ingredient_note"] is None


def test_original_recording_heat_below_threshold_gets_raw_warning_but_is_not_blocked() -> None:
    undercooked = dataclasses.replace(
        ORIGINAL, steps=[AdaptedStep(step_no=1, action="Chần gà", temperature_c=50, duration_sec=60)],
    )
    result = asyncio.run(adapt_or_fallback(undercooked, REQUEST, ScriptedLLM(ValueError("lỗi"))))

    assert result.source == "original"
    assert result.raw_ingredient_warning and result.model_dump()["raw_ingredient_note"] == RAW_INGREDIENT_NOTE


COOKED_STEP = AdaptedStep(step_no=1, action="Kho gà đến chín.", temperature_c=80, duration_sec=900)
SAFE_COMPLETE_ORIGINAL = dataclasses.replace(
    ORIGINAL,
    ingredients=[
        ORIGINAL.ingredients[0],
        dataclasses.replace(ORIGINAL.ingredients[1], amount=20, unit="g", facts_per_100g=Nutrition(35, 5, 3, 0)),
    ],
    steps=[COOKED_STEP],
)


def test_original_with_all_grams_and_safe_step_has_nutrition_and_no_raw_warning() -> None:
    result = asyncio.run(adapt_or_fallback(SAFE_COMPLETE_ORIGINAL, REQUEST, ScriptedLLM(ValueError("lỗi"))))

    assert result.source == "original" and not result.raw_ingredient_warning
    assert result.model_dump()["raw_ingredient_note"] is None
    assert result.nutrition_per_serving.kcal == EXPECTED_KCAL_PER_SERVING + 20 * 35 / 100 / ORIGINAL_SERVINGS
    assert result.model_dump()["nutrition_available"] is True


def test_optional_ingredient_without_grams_does_not_hide_nutrition() -> None:
    optional_sauce = dataclasses.replace(ORIGINAL.ingredients[1], is_optional=True)
    recipe = dataclasses.replace(ORIGINAL, ingredients=[ORIGINAL.ingredients[0], optional_sauce], steps=[COOKED_STEP])
    result = asyncio.run(adapt_or_fallback(recipe, REQUEST, ScriptedLLM(ValueError("lỗi"))))

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


def test_suggest_response_is_accepted_unchanged_by_post_saved() -> None:
    # Client gửi nguyên công thức /recipes/suggest trả (kể cả field tính sẵn) lên POST /saved — không được lệch field.
    for result in (run_adapt(ScriptedLLM(adapted_json(temperature_c=80)), CHICKEN_ONLY), run_adapt(ScriptedLLM(ValueError("x")))):
        wire = json.loads(json.dumps(jsonable_encoder(result)))
        assert SaveRecipeIn.model_validate({"recipe": wire}).recipe == result


def test_suggest_without_ingredients_stops_before_search() -> None:
    empty = SuggestRequest(ingredient_ids=[], diet_type="omnivore", allergens=[])
    with pytest.raises(NoUsableIngredientsError):
        asyncio.run(suggest_recipes(empty, None, None, None, None, ScriptedLLM("{}"), quota_available))


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


async def quota_available() -> None:
    return None


RECIPE_COUNT = 5


def run_suggest_with_fake_search(monkeypatch: pytest.MonkeyPatch, llm: LLMProvider):
    async def fake_catalog(client):
        return CATALOG

    async def fake_search(*args):
        return [ORIGINAL.hit] * RECIPE_COUNT

    async def fake_load(client, hits):
        return [ORIGINAL] * len(hits)

    monkeypatch.setattr(ingredient_normalizer, "load_ingredient_catalog", fake_catalog)
    monkeypatch.setattr(pipeline, "search_recipes", fake_search)
    monkeypatch.setattr(pipeline, "load_original_recipes", fake_load)
    catalog_cache = IngredientCatalogCache(client=None)
    return asyncio.run(suggest_recipes(REQUEST, catalog_cache, None, None, FakeEmbedder(), llm, quota_available))


class EmbedderWaitingForQuota:
    """Embed chỉ xong khi quota_check đã bắt đầu → tuần tự (quota xong rồi mới embed hoặc ngược lại) thì treo."""

    def __init__(self) -> None:
        self.quota_started = asyncio.Event()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        await asyncio.wait_for(self.quota_started.wait(), timeout=1)
        return [[0.0] for _ in texts]


def test_quota_check_runs_alongside_embed_and_must_pass_before_search(monkeypatch: pytest.MonkeyPatch) -> None:
    searched: list[object] = []

    async def fake_catalog(client):
        return CATALOG

    async def spy_search(*args):
        searched.append(args)
        return []

    monkeypatch.setattr(ingredient_normalizer, "load_ingredient_catalog", fake_catalog)
    monkeypatch.setattr(pipeline, "search_recipes", spy_search)

    async def run(quota_ok: bool) -> list:
        embedder = EmbedderWaitingForQuota()

        async def quota_check() -> None:
            embedder.quota_started.set()
            await asyncio.sleep(0.01)
            if not quota_ok:
                raise RateLimitedError("Đã dùng hết lượt hôm nay", 60)

        catalog_cache = IngredientCatalogCache(client=None)
        return await suggest_recipes(REQUEST, catalog_cache, None, None, embedder, ScriptedLLM("{}"), quota_check)

    assert asyncio.run(run(quota_ok=True)) == [] and len(searched) == 1
    with pytest.raises(RateLimitedError):
        asyncio.run(run(quota_ok=False))
    assert len(searched) == 1  # hết lượt → không tìm, không gọi LLM


def test_quota_error_wins_over_embed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenEmbedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("bge-m3 hỏng")

    async def exhausted() -> None:
        raise RateLimitedError("Đã dùng hết lượt hôm nay", 60)

    async def fake_catalog(client):
        return CATALOG

    monkeypatch.setattr(ingredient_normalizer, "load_ingredient_catalog", fake_catalog)
    catalog_cache = IngredientCatalogCache(client=None)
    with pytest.raises(RateLimitedError):
        asyncio.run(suggest_recipes(REQUEST, catalog_cache, None, None, BrokenEmbedder(), ScriptedLLM("{}"), exhausted))


def test_suggest_adapts_only_top_recipe_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(pipeline.LLM_ADAPT_COUNT_ENV, raising=False)
    llm = ScriptedLLM(adapted_json(temperature_c=80))

    results = run_suggest_with_fake_search(monkeypatch, llm)

    assert llm.calls == 1
    assert [result.source for result in results] == ["adapted"] + ["original"] * (RECIPE_COUNT - 1)


def test_suggest_adapt_count_from_env_runs_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(pipeline.LLM_ADAPT_COUNT_ENV, str(RECIPE_COUNT))
    llm = ConcurrencyProbeLLM()

    results = run_suggest_with_fake_search(monkeypatch, llm)

    assert len(results) == RECIPE_COUNT and llm.max_running == RECIPE_COUNT


def test_invalid_adapt_count_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(pipeline.LLM_ADAPT_COUNT_ENV, "mot")
    assert pipeline.llm_adapt_count() == pipeline.DEFAULT_LLM_ADAPT_COUNT


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
    assert set(result.names) == {CHICKEN_ID, 16}


def test_recognize_distinguishes_vision_error_from_no_food() -> None:
    with pytest.raises(VisionUnavailableError):
        run_recognize(ScriptedVision(VisionUnavailableError("timeout")))
    with pytest.raises(NoUsableIngredientsError):
        run_recognize(ScriptedVision(Detected(ingredients=[], uncertain=[])))


EGG = safety_rule_from_row(next(row for row in FOOD_SAFETY_THRESHOLDS if row["category"] == "egg_dish"))
EGG_ID, HONEY_ID = 101, 154
# Bước thật của món 2647 "Trứng Gà Ngâm Mật Ong": không bước nào làm nóng ("làm chín" ở đây là mật ong).
HONEY_EGG_STEPS = [
    "Bạn chọn 9 quả trứng gà ta rồi tách riêng lòng đỏ và lòng trắng ra tô, sau đó cho lòng đỏ trứng gà vào một lọ "
    "thủy tinh, nhẹ nhàng đổ 200 ml mật ong ngập bề mặt trứng rồi đậy kín nắp.",
    "Để bảo quản, tốt nhất bạn nên đặt lọ trứng ngâm mật ong này ở nơi khô thoáng hoặc tủ mát, sau 1 ngày ngâm bạn dùng "
    "muỗng nhẹ tay lật mặt trứng còn lại giúp mật ong làm chín trứng đều.",
    "Bạn nên ăn 1 lòng đỏ trứng gà ngâm mật ong trước bữa tối khoảng 20 phút.",
]
HONEY_EGG = OriginalRecipe(
    hit=SearchHit(recipe_id=2647, title="Trứng Gà Ngâm Mật Ong", servings=2, score=0.7),
    ingredients=[
        RecipeIngredientInfo(EGG_ID, "Trứng gà", None, None, EGG, frozenset({"egg"}), None),
        RecipeIngredientInfo(HONEY_ID, "Mật ong", 200, "g", None, frozenset(), None),
    ],
    steps=[AdaptedStep(step_no=i, action=text, temperature_c=None, duration_sec=None)
           for i, text in enumerate(HONEY_EGG_STEPS, start=1)],
)


def original_of(recipe: OriginalRecipe):
    return asyncio.run(adapt_or_fallback(recipe, REQUEST, ScriptedLLM(ValueError("lỗi"))))


def test_raw_egg_recipe_without_heating_step_gets_raw_warning() -> None:
    result = original_of(HONEY_EGG)

    assert result.source == "original" and result.raw_ingredient_warning
    assert result.model_dump()["raw_ingredient_note"] == (
        "Món này có thể dùng nguyên liệu sống hoặc chưa nấu chín — "
        "không phù hợp cho trẻ nhỏ, phụ nữ mang thai, người miễn dịch yếu"
    )


@pytest.mark.parametrize("cooking_step", [
    "Đun nóng dầu, cho gà vào chiên vàng đều hai mặt.",
    "Chuẩn bị chảo có láng dầu ăn, để sôi già rồi múc bột vào.",
    "Đút lò trong 20 phút ở 180 độ C.",
    "fry the chicken until golden",
    "bake at 350 degrees for 25 minutes",
])
def test_raw_risk_recipe_with_a_heating_step_has_no_raw_warning(cooking_step: str) -> None:
    fried = dataclasses.replace(ORIGINAL, steps=[
        AdaptedStep(step_no=1, action="Ướp gà với nước mắm 15 phút.", temperature_c=None, duration_sec=None),
        AdaptedStep(step_no=2, action=cooking_step, temperature_c=None, duration_sec=None),
    ])
    assert not original_of(fried).raw_ingredient_warning


def test_no_meat_fish_or_egg_means_no_raw_warning_even_without_heating() -> None:
    salad = dataclasses.replace(HONEY_EGG, ingredients=HONEY_EGG.ingredients[1:])  # chỉ còn mật ong
    assert not original_of(salad).raw_ingredient_warning
