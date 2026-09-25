"""Bước [4] workflow: map tên nguyên liệu thô (Việt/Anh, có thể kèm số lượng) về ingredient_id bằng fuzzy match."""

import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz, process
from supabase import AsyncClient

from app.services.ingredient_matching import (
    CatalogIngredient,
    IngredientMatcher,
    all_names,
    normalize_exact,
    strip_diacritics,
)

AUTO_ACCEPT_SCORE = 90
UNCERTAIN_MIN_SCORE = 75
EXACT_MATCH_SCORE = 100

# Đơn vị chỉ bị bỏ khi đứng ngay sau một con số — "2 củ hành" → "hành", nhưng "củ cải" giữ nguyên.
UNITS = (
    "muỗng canh", "muỗng cà phê", "thìa canh", "thìa cà phê", "muỗng", "thìa", "gram", "gr", "g", "kg",
    "ml", "lít", "l", "chén", "bát", "cốc", "ly", "quả", "trái", "củ", "cây", "nhánh", "tép", "lá",
    "miếng", "lát", "gói", "hộp", "con", "bó", "nắm", "tablespoons", "tablespoon", "tbsp", "teaspoons",
    "teaspoon", "tsp", "cups", "cup", "oz", "lbs", "lb", "pounds", "pound", "cloves", "clove",
    "pieces", "piece", "slices", "slice", "bunch", "cans", "can", "pinch",
)
# Tính từ chế biến / từ đệm không thuộc tên nguyên liệu. Không có "khô" vì "tôm khô" là nguyên liệu riêng.
PREPARATION_WORDS = (
    "băm nhỏ", "thái nhỏ", "cắt nhỏ", "xắt nhỏ", "đập dập", "rửa sạch", "bỏ hạt", "bỏ vỏ", "sơ chế",
    "băm", "thái", "cắt", "xắt", "nhỏ", "tươi", "luộc", "chiên", "nướng",
    "finely", "roughly", "chopped", "diced", "minced", "sliced", "grated", "peeled", "crushed",
    "fresh", "raw", "frozen", "cooked", "boiled", "fried", "large", "medium", "small", "of",
)

_NUMBER = r"\d+(?:[.,/]\d+)?"
_PARENTHESIZED = re.compile(r"\([^)]*\)")
_QUANTITY_WITH_UNIT = re.compile(rf"{_NUMBER}\s*(?:(?:{'|'.join(UNITS)})\b)?")
_PREPARATION = re.compile(rf"\b(?:{'|'.join(PREPARATION_WORDS)})\b")
_PUNCTUATION = re.compile(r"[^\w\s]")

AliasTable = dict[str, set[int]]


class MatchStatus(str, Enum):
    ACCEPTED = "accepted"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IngredientMatch:
    """Kết quả map 1 tên thô; ingredient_id là ứng viên tốt nhất (None khi reject)."""

    raw_name: str
    ingredient_id: int | None
    score: float
    status: MatchStatus


def clean_ingredient_name(raw_name: str) -> str:
    """Bỏ phần trong ngoặc, số lượng + đơn vị, tính từ chế biến, dấu câu: "500g thịt bò, băm nhỏ" → "thịt bò"."""
    text = _PARENTHESIZED.sub(" ", normalize_exact(raw_name))
    text = _QUANTITY_WITH_UNIT.sub(" ", text)
    text = _PUNCTUATION.sub(" ", text)
    text = _PREPARATION.sub(" ", text)
    return " ".join(text.split())


class IngredientNormalizer:
    """Khớp chính xác trước (IngredientMatcher), sau đó token_set_ratio trên tên có dấu và bản bỏ dấu."""

    def __init__(self, catalog: Iterable[CatalogIngredient]) -> None:
        catalog = list(catalog)
        self._exact_matcher = IngredientMatcher(catalog)
        self._accented_choices = _build_choices(catalog, normalize_exact)
        self._unaccented_choices = _build_choices(catalog, strip_diacritics)

    def normalize(self, raw_names: list[str]) -> list[IngredientMatch]:
        """Map từng tên thô, giữ đúng thứ tự input."""
        return [self._match_one(raw_name) for raw_name in raw_names]

    def _match_one(self, raw_name: str) -> IngredientMatch:
        cleaned = clean_ingredient_name(raw_name)
        if not cleaned:
            return IngredientMatch(raw_name, None, 0, MatchStatus.REJECTED)
        exact_id = self._exact_matcher.match(cleaned)
        if exact_id is not None:
            return IngredientMatch(raw_name, exact_id, EXACT_MATCH_SCORE, MatchStatus.ACCEPTED)
        # max() giữ phần tử đầu khi bằng điểm → ưu tiên kết quả trên tên có dấu.
        ingredient_id, score, is_tie = max(
            _best_candidate(cleaned, self._accented_choices),
            _best_candidate(strip_diacritics(cleaned), self._unaccented_choices),
            key=lambda candidate: candidate[1],
        )
        return IngredientMatch(raw_name, ingredient_id, score, _status_for(score, is_tie))


def accepted_ingredient_ids(matches: list[IngredientMatch]) -> list[int]:
    """ingredient_id đã tự nhận (không trùng), dùng thẳng cho bước gợi ý công thức."""
    accepted = (match.ingredient_id for match in matches if match.status is MatchStatus.ACCEPTED)
    return list(dict.fromkeys(accepted))


async def load_ingredient_catalog(client: AsyncClient) -> list[CatalogIngredient]:
    """Đọc bảng ingredients (tên Việt, Anh, aliases) để dựng IngredientNormalizer."""
    # ponytail: 1 request, đủ khi bảng < 1000 dòng (giới hạn mặc định PostgREST); vượt thì phân trang .range().
    response = await client.table("ingredients").select("id,name_vi,name_en,aliases").execute()
    return [
        CatalogIngredient(
            id=row["id"], name_vi=row["name_vi"], name_en=row["name_en"], aliases=tuple(row["aliases"] or ()),
        )
        for row in response.data
    ]


def _build_choices(catalog: list[CatalogIngredient], normalize_name: Callable[[str], str]) -> AliasTable:
    """Bảng alias → các ingredient_id; 1 alias có thể thuộc nhiều nguyên liệu (bỏ dấu "Me"/"Mè" → "me")."""
    choices: AliasTable = defaultdict(set)
    for ingredient in catalog:
        for name in all_names(ingredient):
            choices[normalize_name(name)].add(ingredient.id)
    return dict(choices)


def _best_candidate(query: str, choices: AliasTable) -> tuple[int | None, float, bool]:
    """(id tốt nhất, điểm, có hoà điểm giữa nhiều nguyên liệu không); dưới UNCERTAIN_MIN_SCORE → (None, 0, False)."""
    results = process.extract(
        query, list(choices), scorer=fuzz.token_set_ratio, processor=None,
        score_cutoff=UNCERTAIN_MIN_SCORE, limit=None,
    )
    if not results:
        return None, 0, False
    top_score = results[0][1]
    top_ids = set().union(*(choices[name] for name, score, _ in results if score == top_score))
    return min(top_ids), top_score, len(top_ids) > 1


def _status_for(score: float, is_tie: bool) -> MatchStatus:
    """Hoà điểm giữa nhiều nguyên liệu thì không tự nhận, để user chọn."""
    if score >= AUTO_ACCEPT_SCORE and not is_tie:
        return MatchStatus.ACCEPTED
    if score >= UNCERTAIN_MIN_SCORE:
        return MatchStatus.UNCERTAIN
    return MatchStatus.REJECTED
