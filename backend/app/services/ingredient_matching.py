"""Map tên nguyên liệu (từ vision model hoặc user nhập) về ingredient_id trong bảng ingredients."""

import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogIngredient:
    """Một dòng ingredients đủ để so khớp tên."""

    id: int
    name_vi: str
    aliases: tuple[str, ...] = ()
    name_en: str | None = None


def normalize_exact(text: str) -> str:
    """Chuẩn hoá giữ nguyên dấu: NFC (gõ dựng sẵn/tổ hợp như nhau), bỏ khoảng trắng thừa, không phân biệt hoa thường."""
    return " ".join(unicodedata.normalize("NFC", text).split()).casefold()


def strip_diacritics(text: str) -> str:
    """Bỏ dấu tiếng Việt ("Đậu phụ" → "dau phu") để khớp khi user gõ không dấu."""
    decomposed = unicodedata.normalize("NFD", normalize_exact(text))
    return "".join(char for char in decomposed if not unicodedata.combining(char)).replace("đ", "d")


def has_diacritics(text: str) -> bool:
    """Có dấu tiếng Việt (hoặc chữ đ) hay không — tên không dấu mới cần so khớp bản bỏ dấu."""
    return strip_diacritics(text) != normalize_exact(text)


def all_names(ingredient: CatalogIngredient) -> tuple[str, ...]:
    """Mọi tên dùng để khớp: tên Việt, tên Anh (nếu có) và aliases."""
    english = (ingredient.name_en,) if ingredient.name_en else ()
    return (ingredient.name_vi, *english, *ingredient.aliases)


class IngredientMatcher:
    """Khớp tên có dấu trước; chỉ fallback bản bỏ dấu khi không có khớp chính xác và kết quả duy nhất."""

    def __init__(self, catalog: Iterable[CatalogIngredient]) -> None:
        self._exact_index: dict[str, set[int]] = defaultdict(set)
        self._unaccented_index: dict[str, set[int]] = defaultdict(set)
        for ingredient in catalog:
            for name in all_names(ingredient):
                self._exact_index[normalize_exact(name)].add(ingredient.id)
                self._unaccented_index[strip_diacritics(name)].add(ingredient.id)

    def match(self, name: str) -> int | None:
        """Trả ingredient_id, hoặc None nếu không khớp hay mơ hồ (vd "mé" có thể là "Me" hoặc "Mè")."""
        exact_ids = self._exact_index.get(normalize_exact(name), set())
        if exact_ids:
            return _single_or_none(exact_ids)
        # Tên đã gõ dấu thì dấu là thông tin thật: "bò" (thịt) ≠ "bơ" (butter) dù cùng bỏ dấu thành "bo".
        if has_diacritics(name):
            return None
        return _single_or_none(self._unaccented_index.get(strip_diacritics(name), set()))


def _single_or_none(ids: set[int]) -> int | None:
    """Chỉ trả id khi đúng 1 ứng viên — nhiều ứng viên thì để user xác nhận, không đoán."""
    return next(iter(ids)) if len(ids) == 1 else None
