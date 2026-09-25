"""Test map tên → ingredient_id, đặc biệt các cặp chỉ khác nhau ở dấu."""

import unicodedata

from app.services.ingredient_matching import CatalogIngredient, IngredientMatcher

TAMARIND_ID = 1
SESAME_ID = 2
TOFU_ID = 3

MATCHER = IngredientMatcher([
    CatalogIngredient(id=TAMARIND_ID, name_vi="Me"),
    CatalogIngredient(id=SESAME_ID, name_vi="Mè"),
    CatalogIngredient(id=TOFU_ID, name_vi="Đậu phụ", aliases=("Đậu hũ",)),
])


def test_me_and_me_with_accent_never_cross_match() -> None:
    assert MATCHER.match("me") == TAMARIND_ID
    assert MATCHER.match("mè") == SESAME_ID
    assert MATCHER.match("Mè") == SESAME_ID


def test_exact_match_handles_decomposed_unicode() -> None:
    decomposed_sesame = unicodedata.normalize("NFD", "mè")
    assert MATCHER.match(decomposed_sesame) == SESAME_ID


def test_unaccented_fallback_when_no_exact_match() -> None:
    assert MATCHER.match("dau phu") == TOFU_ID
    assert MATCHER.match("  DAU   HU ") == TOFU_ID


def test_ambiguous_unaccented_match_returns_none() -> None:
    # "mé" không khớp chính xác; bỏ dấu thành "me" → cả Me lẫn Mè → không đoán
    assert MATCHER.match("mé") is None


def test_unknown_name_returns_none() -> None:
    assert MATCHER.match("thịt khủng long") is None
