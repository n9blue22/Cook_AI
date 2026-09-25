"""Test map tên thô Việt/Anh → ingredient_id: làm sạch input, ngưỡng fuzzy, không đoán khi mơ hồ."""

import pytest

from app.services.ingredient_matching import CatalogIngredient
from app.services.ingredient_normalizer import (
    IngredientNormalizer,
    MatchStatus,
    accepted_ingredient_ids,
    clean_ingredient_name,
)

BEEF_ID = 1
PORK_ID = 2
TOMATO_ID = 3
GARLIC_ID = 4
TOFU_ID = 5
TAMARIND_ID = 6
SESAME_ID = 7
RADISH_ID = 8

NORMALIZER = IngredientNormalizer([
    CatalogIngredient(id=BEEF_ID, name_vi="Thịt bò", name_en="Beef"),
    CatalogIngredient(id=PORK_ID, name_vi="Thịt heo", name_en="Pork", aliases=("Thịt lợn",)),
    CatalogIngredient(id=TOMATO_ID, name_vi="Cà chua", name_en="Tomato"),
    CatalogIngredient(id=GARLIC_ID, name_vi="Tỏi", name_en="Garlic"),
    CatalogIngredient(id=TOFU_ID, name_vi="Đậu phụ", name_en="Tofu", aliases=("Đậu hũ",)),
    CatalogIngredient(id=TAMARIND_ID, name_vi="Me", name_en="Tamarind"),
    CatalogIngredient(id=SESAME_ID, name_vi="Mè", name_en="Sesame"),
    CatalogIngredient(id=RADISH_ID, name_vi="Củ cải", name_en="Radish"),
])


def _match(raw_name: str):
    return NORMALIZER.normalize([raw_name])[0]


@pytest.mark.parametrize(("raw_name", "expected"), [
    ("500g thịt bò, băm nhỏ", "thịt bò"),
    ("2 muỗng canh tỏi băm", "tỏi"),
    ("3 quả cà chua (chín)", "cà chua"),
    ("1 củ củ cải", "củ cải"),
    ("2 cloves garlic, minced", "garlic"),
    ("1/2 cup of chopped fresh tomato", "tomato"),
    ("200 g Tofu", "tofu"),
])
def test_clean_strips_quantity_unit_and_preparation(raw_name: str, expected: str) -> None:
    assert clean_ingredient_name(raw_name) == expected


def test_unit_word_kept_when_not_after_number() -> None:
    assert clean_ingredient_name("củ cải") == "củ cải"


@pytest.mark.parametrize(("raw_name", "expected_id"), [
    ("500g thịt bò băm", BEEF_ID),
    ("Thịt lợn", PORK_ID),
    ("dau hu", TOFU_ID),
    ("thit bo", BEEF_ID),
    ("2 cloves garlic, minced", GARLIC_ID),
    ("Fresh Tomato", TOMATO_ID),
    ("ground beef", BEEF_ID),
])
def test_vietnamese_and_english_names_are_accepted(raw_name: str, expected_id: int) -> None:
    match = _match(raw_name)
    assert match.status is MatchStatus.ACCEPTED
    assert match.ingredient_id == expected_id


def test_typo_is_accepted_via_fuzzy_score() -> None:
    match = _match("ca chuaa")
    assert match.status is MatchStatus.ACCEPTED
    assert match.ingredient_id == TOMATO_ID
    assert match.score >= 90


def test_mid_score_is_uncertain_with_candidate() -> None:
    match = _match("tomatoes")
    assert match.status is MatchStatus.UNCERTAIN
    assert match.ingredient_id == TOMATO_ID


def test_ambiguous_name_is_uncertain_not_guessed() -> None:
    # "thịt" khớp 100 với cả thịt bò lẫn thịt heo; "mé" bỏ dấu khớp cả Me lẫn Mè
    assert _match("thịt").status is MatchStatus.UNCERTAIN
    assert _match("mé").status is MatchStatus.UNCERTAIN


def test_accents_decide_between_me_and_me() -> None:
    assert _match("mè").ingredient_id == SESAME_ID
    assert _match("me").ingredient_id == TAMARIND_ID


@pytest.mark.parametrize("raw_name", ["thịt khủng long", "dragon fruit", "500g", "   "])
def test_unknown_or_empty_is_rejected(raw_name: str) -> None:
    match = _match(raw_name)
    assert match.status is MatchStatus.REJECTED
    assert match.ingredient_id is None


def test_normalize_keeps_order_and_accepted_ids_dedupe() -> None:
    matches = NORMALIZER.normalize(["tỏi", "thịt khủng long", "garlic", "đậu phụ"])
    assert [match.raw_name for match in matches] == ["tỏi", "thịt khủng long", "garlic", "đậu phụ"]
    assert accepted_ingredient_ids(matches) == [GARLIC_ID, TOFU_ID]
