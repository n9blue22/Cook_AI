"""Gia vị cơ bản không bị mất khi user không tick: DB thật + Groq thật (không mock). Thiếu key thì skip, Groq 429 thì skip."""

import asyncio
import os
import re

import pytest

from app.core.config import get_settings
from app.core.supabase_client import create_admin_client
from app.services.llm.groq_adapter import GroqAdapter
from app.services.llm.provider import LLMUnavailableError
from app.services.llm.recipe_adaptation import ADAPT_RECIPE_SYSTEM_PROMPT, AdaptedRecipe, LLMAdaptedRecipe
from app.services.pantry_basics import is_always_available, restore_pantry_basics
from app.services.pipeline import SuggestRequest, build_adapt_user_prompt
from app.services.recipe_repository import SearchHit, load_original_recipes

# Heo Quay Bằng Nồi Chiên Không Dầu: Muối + Đường có trong danh sách và bước ướp "1 muỗng cà phê đường 1 muỗng cà phê muối".
# Repro trước khi sửa: Groq bỏ cả 2 khỏi ingredients lẫn steps khi user chỉ tick Hành tím, Tỏi, Gừng, Thịt nạc vai heo.
ROAST_PORK_ID = 2287
SEASONING_WITH_QUANTITY = {  # "khứa vài đường" (vết dao) không tính là nêm đường → bắt buộc có số lượng phía trước
    "Muối": re.compile(r"muối", re.IGNORECASE),
    "Đường": re.compile(r"\d[^.;]{0,25}\bđường", re.IGNORECASE),
}


async def adapt_without_ticked_basics() -> tuple[AdaptedRecipe, set[str]]:
    admin = await create_admin_client(get_settings())
    [original] = await load_original_recipes(admin, [SearchHit(ROAST_PORK_ID, "", 1, 1.0)])
    ticked = [item.ingredient_id for item in original.ingredients if not is_always_available(item.name_vi)]
    prompt = build_adapt_user_prompt(original, SuggestRequest(ticked, "omnivore", []))
    raw = await GroqAdapter().generate_json(ADAPT_RECIPE_SYSTEM_PROMPT, prompt, LLMAdaptedRecipe)
    adapted = restore_pantry_basics(LLMAdaptedRecipe.model_validate_json(raw).to_adapted(), original)
    names = {item.ingredient_id: item.name_vi for item in original.ingredients}
    return adapted, {names[item.ingredient_id] for item in adapted.ingredients}


@pytest.mark.skipif(
    not (os.getenv("GROQ_API_KEY") and os.getenv("SUPABASE_SECRET_KEY")), reason="cần GROQ_API_KEY + SUPABASE_SECRET_KEY",
)
def test_basic_seasonings_survive_in_ingredients_and_steps_when_user_did_not_tick_them() -> None:
    try:
        adapted, kept_names = asyncio.run(adapt_without_ticked_basics())
    except LLMUnavailableError as error:
        pytest.skip(f"Groq 429/timeout: {error}")

    assert {"Muối", "Đường"} <= kept_names  # (a) danh sách
    steps_text = " ".join(step.action for step in adapted.steps)
    missing_in_steps = [name for name, pattern in SEASONING_WITH_QUANTITY.items() if not pattern.search(steps_text)]
    assert not missing_in_steps, f"(b) bước nấu mất câu nêm {missing_in_steps}: {steps_text}"
