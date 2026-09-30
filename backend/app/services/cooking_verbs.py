"""Dò động từ nấu ăn trong câu hướng dẫn (Việt + Anh, kể cả dạng chia tiếng Anh).

Dùng chung cho dọn bước cuối (scripts/step_cleaning.py) và cảnh báo nguyên liệu sống (recipe_results.py).
"""

import re

from app.services.ingredient_matching import normalize_exact

# Chỉ động từ LÀM NÓNG thực phẩm — tập con của động từ hướng dẫn trong step_cleaning ("cho", "ngâm", "để" không làm
# chín gì). Bỏ các từ mơ hồ: "phi" (phi hành, không làm chín thịt), "tráng" (tráng nước), "quay" (quay lại), "nhúng",
# "sấy"; tiếng Anh bỏ "brown" (brown sugar), "toast" (serve on toast), "smoke".
VIETNAMESE_HEAT_VERBS = (
    "nấu", "chiên", "rán", "luộc", "xào", "hấp", "đun", "nướng", "kho", "hầm", "om", "rim", "rang", "chần", "trụng",
    "sên", "hâm", "áp chảo", "lên bếp", "sôi", "đút lò", "vào lò",  # "để chảo lên bếp", "dầu sôi già"
    # Không có "chín": "mật ong làm chín trứng" (trứng ngâm mật ong) không dùng nhiệt.
)
ENGLISH_HEAT_VERBS = (
    "cook", "bake", "boil", "simmer", "fry", "saute", "grill", "roast", "broil", "microwave", "steam", "sear",
    "poach", "reheat", "heat", "preheat", "bbq", "barbecue", "scramble", "caramelize", "warm",
)
# Câu ghi nhiệt độ ("180 độ C", "350°F", "350 degrees") = có làm nóng.
STATED_TEMPERATURE = r"\d+\s*(?:°\s*[cf]|độ\s*[cf]|degrees?)"


def english_verb_forms(verb: str) -> str:
    """bake → bake|bakes|baked|baking; chop → chops|chopped|chopping; fry → fries|fried."""
    if verb.endswith("e"):
        return rf"{verb[:-1]}(?:e|es|ed|ing)"
    if verb.endswith("y") and verb[-2] not in "aeiou":
        return rf"{verb[:-1]}(?:y|ies|ied|ying)"
    return rf"{verb}(?:{verb[-1]})?(?:s|es|ed|ing)?"


def verb_pattern(vietnamese: tuple[str, ...], english: tuple[str, ...], extra: str = "") -> re.Pattern[str]:
    """Regex khớp nguyên từ: động từ Việt nguyên văn + mọi dạng chia của động từ Anh (+ mẫu thêm nếu có)."""
    alternatives = [*map(re.escape, vietnamese), *map(english_verb_forms, english)]
    return re.compile(r"\b(?:" + "|".join(alternatives) + (f"|{extra}" if extra else "") + r")\b")


_HEAT_VERB = verb_pattern(VIETNAMESE_HEAT_VERBS, ENGLISH_HEAT_VERBS, extra=STATED_TEMPERATURE)


def has_heat_cooking_verb(text: str) -> bool:
    """Câu có động từ làm nóng thực phẩm (nấu, chiên, bake, boil...)."""
    return bool(_HEAT_VERB.search(normalize_exact(text)))
