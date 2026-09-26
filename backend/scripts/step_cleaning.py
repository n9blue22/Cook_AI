"""Dọn bước CUỐI của công thức: bỏ câu quảng cáo/cảm thán, bỏ cả bước nếu không còn hướng dẫn nấu nào.

Chỉ đụng bước cuối — các bước giữa là hướng dẫn thật. Mẫu câu lấy từ dữ liệu ViFoodRec/Food.com thật
("Xin mời", "Tiết trời se lạnh là thời điểm vàng...", "this recipe yields 1 3 / 4 cups").
Khi nghi ngờ thì GIỮ: xoá nhầm hướng dẫn thật tệ hơn để sót 1 câu cảm thán.
"""

import re

from app.services.ingredient_matching import normalize_exact

VIETNAMESE_COOKING_VERBS = (
    "cho", "trộn", "nấu", "chiên", "luộc", "ướp", "xào", "hấp", "nêm", "rưới", "rắc", "đun", "bắc", "đổ", "thêm",
    "khuấy", "đảo", "cắt", "thái", "băm", "rửa", "ngâm", "phi", "nướng", "kho", "hầm", "om", "rim", "xếp", "gói",
    "cuốn", "lăn", "nhúng", "tráng", "đánh", "nhồi", "ủ", "múc", "bày", "dọn", "trang trí", "chấm", "vắt", "lọc",
    "pha", "giã", "xay", "vớt", "gắp", "chan", "rải", "phết", "quết", "tắt", "hạ lửa", "cuộn", "chần", "trụng",
    "sên", "ép", "bóc", "gọt", "nặn", "đậy", "để nguội", "bảo quản", "hâm", "chia", "rót", "tưới", "bóp", "dùng",
    "lấy", "nhấc", "đợi", "thực hiện", "lật", "rang", "sấy", "đổ khuôn", "phủ", "quét", "tạo hình", "ăn kèm", "để",
    "giữ", "trình bày",
)
ENGLISH_COOKING_VERBS = (
    "add", "stir", "mix", "combine", "cook", "bake", "boil", "simmer", "fry", "saute", "heat", "pour", "sprinkle",
    "season", "place", "put", "serve", "garnish", "top", "whisk", "beat", "blend", "chill", "refrigerate", "freeze",
    "cover", "drain", "cut", "slice", "chop", "spread", "roll", "brush", "remove", "transfer", "let", "arrange",
    "toss", "grill", "roast", "broil", "microwave", "melt", "fold", "knead", "spoon", "drizzle", "squeeze",
    "preheat", "dip", "coat", "fill", "wrap", "cool", "store", "reheat", "divide", "shape", "press", "layer", "rub",
    "marinate", "steam", "return", "turn", "reduce", "bring", "allow", "repeat", "puree", "strain", "continue",
    "finish", "adjust", "taste", "check", "flip", "sear", "brown", "soak", "rinse", "peel", "grate", "mash", "scoop",
    "insert", "wait", "leave", "keep", "stand", "rest", "slather", "use", "make", "prepare", "assemble", "sift",
    "dust", "separate", "increase", "decrease", "eat", "watch", "dry", "process", "baste", "crumble", "bbq",
    "barbecue", "fluff", "pass", "scatter", "decorate", "splash", "discard", "shake", "skim", "thicken", "dice",
    "mince", "whip", "grease", "line", "pat", "lay", "set", "dollop", "squirt", "give", "cube", "debone", "trim", "throw",
)
# Luôn là quảng cáo/cảm thán, kể cả khi câu có động từ ("Hãy cùng chúng tôi trổ tài nấu ăn...").
STRONG_PROMO_PHRASES = (
    "hãy cùng", "chúc bạn", "chúc các bạn", "chúc cả nhà", "còn gì tuyệt vời", "tuyệt vời biết mấy", "nghe thôi",
    "xin mời", "trổ tài", "đúng không", "thèm lắm", "tiết trời", "vào những ngày", "quây quần", "lên ngôi",
    "this recipe yields", "this recipe makes", "recipe courtesy", "hope you", "you will love",
)
# Chỉ tính là cảm thán khi câu KHÔNG có động từ nấu ("Múc ra tô, thưởng thức nóng" vẫn là hướng dẫn).
WEAK_PROMO_PHRASES = (
    "thưởng thức", "ngon miệng", "hấp dẫn", "cả nhà", "cả gia đình", "thật tuyệt", "enjoy", "yum", "delicious",
)

# Tín hiệu độ chín / lưu ý ("fish should flake easily when done", "be careful not to overcook") — là hướng dẫn
# dù không có động từ nấu thông thường; KHÔNG coi là quảng cáo.
DONENESS_OR_CAUTION_PHRASES = ("should", "be careful", "until done", "when done", "done when", "ready when", "make sure")

# Hết câu: sau . ! ? … (kể cả thiếu dấu cách "tương cà chua.Chúc"), hoặc ngay trước "Chúc" / ", chúc".
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s*(?=[^\W\d_])|\s+(?=Chúc\b)|,\s*(?=chúc\b)")


def _english_verb_forms(verb: str) -> str:
    """bake → bake|bakes|baked|baking; chop → chops|chopped|chopping; fry → fries|fried."""
    if verb.endswith("e"):
        return rf"{verb[:-1]}(?:e|es|ed|ing)"
    if verb.endswith("y") and verb[-2] not in "aeiou":
        return rf"{verb[:-1]}(?:y|ies|ied|ying)"
    return rf"{verb}(?:{verb[-1]})?(?:s|es|ed|ing)?"


def _phrase_pattern(phrases: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{'|'.join(map(re.escape, phrases))})\b")


_COOKING_VERB = re.compile(
    r"\b(?:"
    + "|".join([*map(re.escape, VIETNAMESE_COOKING_VERBS), *map(_english_verb_forms, ENGLISH_COOKING_VERBS)])
    + r"|to taste|until)\b"
)
_STRONG_PROMO = _phrase_pattern(STRONG_PROMO_PHRASES)
_WEAK_PROMO = _phrase_pattern(WEAK_PROMO_PHRASES)
# Thêm: tránh nấu quá chín ("don't overcook them"), mốc thời gian ("35 minute depending on thickness",
# "at least an hour ... room temperature") và "done" đứng riêng ("the eggs will be broken up when then are done").
_DONENESS_OR_CAUTION = re.compile(
    _phrase_pattern(DONENESS_OR_CAUTION_PHRASES).pattern
    + r"|\bovercook\w*|\b\d+\s*minutes?\b|\b(?:\d+|an?)\s*hours?\b|\bdone\b"
)


def has_cooking_verb(text: str) -> bool:
    """Có ít nhất 1 động từ nấu ăn (Việt hoặc Anh, kể cả dạng chia)."""
    return bool(_COOKING_VERB.search(normalize_exact(text)))


def is_instruction(sentence: str) -> bool:
    """Hướng dẫn: có động từ nấu, hoặc là tín hiệu độ chín / lưu ý."""
    return has_cooking_verb(sentence) or bool(_DONENESS_OR_CAUTION.search(normalize_exact(sentence)))


def is_promo_sentence(sentence: str) -> bool:
    """Câu quảng cáo/cảm thán, không phải hướng dẫn."""
    text = normalize_exact(sentence)
    return bool(_STRONG_PROMO.search(text)) or (bool(_WEAK_PROMO.search(text)) and not is_instruction(sentence))


def clean_final_step(step: str) -> str | None:
    """Bước cuối đã bỏ câu quảng cáo; None nếu không còn hướng dẫn nấu nào (→ xoá cả bước)."""
    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(step.strip()) if sentence.strip()]
    kept = [sentence for sentence in sentences if not is_promo_sentence(sentence)]
    if not kept or not any(is_instruction(sentence) for sentence in kept):
        return None
    return step.strip() if len(kept) == len(sentences) else " ".join(kept)


def clean_steps(steps: list[str]) -> list[str]:
    """Áp clean_final_step cho bước cuối; công thức 1 bước thì giữ nguyên (không để công thức rỗng)."""
    if len(steps) < 2:
        return steps
    final_step = clean_final_step(steps[-1])
    return steps[:-1] if final_step is None else [*steps[:-1], final_step]
