"""Test từ đa nghĩa tiếng Việt: bơ (butter/quả bơ/bơ hạt), tép, lòng, bản "chay" — các ca lấy từ dữ liệu thật."""

import pytest

from scripts.ingredient_senses import (
    guess_allergen_ids,
    is_non_dairy_lookalike,
    is_vegetarian_version,
    mentions_animal_derived,
    mentions_meat,
    resolve_ambiguous_name,
)

SLUGS = {
    slug: allergen_id
    for allergen_id, slug in enumerate(
        ("egg", "dairy", "wheat", "soy", "peanut", "tree_nuts", "sesame", "fish", "shellfish", "molluscs"), start=1,
    )
}


def _slugs(names: list[str]) -> set[str]:
    by_id = {allergen_id: slug for slug, allergen_id in SLUGS.items()}
    return {by_id[allergen_id] for allergen_id in guess_allergen_ids(names, SLUGS)}


@pytest.mark.parametrize(("name", "title", "expected"), [
    ("bơ", "Sinh Tố Bơ", "quả bơ"),
    ("bơ", "Chè Bơ Viên Nước Cốt Dừa", "quả bơ"),
    ("bơ", "Kem Bơ Dừa", "quả bơ"),
    ("bơ", "Salad Rau Bina Trái Cây", "quả bơ"),
    ("bơ", "Tôm Hùm Nướng Bơ Tỏi", "bơ"),
    ("bơ", "Bánh Bông Lan Trứng", "bơ"),
    ("bơ lạt", "Sinh Tố Bơ", "bơ lạt"),
])
def test_standalone_bo_resolves_by_dish(name: str, title: str, expected: str) -> None:
    assert resolve_ambiguous_name(name, title) == expected


@pytest.mark.parametrize(("name", "expected"), [
    ("bơ lạt", {"dairy"}), ("bơ nhạt", {"dairy"}), ("bơ", {"dairy"}),
    ("trái bơ", set()), ("bơ sáp chín", set()),
    ("bơ đậu phộng", {"peanut"}), ("bơ hạnh nhân", {"tree_nuts"}), ("bơ mè tahini", {"sesame"}),
    ("peanut butter", {"peanut"}), ("unsalted butter", {"dairy"}),
])
def test_bo_allergens(name: str, expected: set[str]) -> None:
    assert _slugs([name]) == expected


def test_nut_butter_and_avocado_are_not_animal_derived() -> None:
    assert not mentions_animal_derived("bơ đậu phộng")
    assert not mentions_animal_derived("trái bơ")
    assert mentions_animal_derived("bơ lạt")
    assert is_non_dairy_lookalike("bơ sáp") and not is_non_dairy_lookalike("bơ lạt")


@pytest.mark.parametrize(("name", "expected"), [
    ("tỏi tép", False), ("tép tỏi", False), ("tép cam", False), ("tép khô", True),
    ("lòng đỏ trứng", False), ("lòng trắng trứng gà", False), ("lòng bò", True), ("trứng cá", True),
    ("gân bò", True), ("cá cam", True), ("cải bó xôi", False),
])
def test_mentions_meat(name: str, expected: bool) -> None:
    assert mentions_meat(name) is expected


def test_segment_tep_is_not_shellfish() -> None:
    assert _slugs(["tỏi tép"]) == set()
    assert _slugs(["tép khô"]) == {"shellfish"}


def test_vegetarian_version() -> None:
    assert is_vegetarian_version("dầu hào chay")
    assert is_vegetarian_version("vegetarian worcestershire sauce")
    assert not is_vegetarian_version("dầu hào")
