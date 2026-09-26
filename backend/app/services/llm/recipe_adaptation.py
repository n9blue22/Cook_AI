"""Schema output và system prompt cho bước LLM điều chỉnh công thức (feature-spec mục 4 bước [8], mục 5 lớp 3)."""

from pydantic import BaseModel


class AdaptedIngredient(BaseModel):
    """Một nguyên liệu trong công thức đã chỉnh; ingredient_id phải lấy từ công thức gốc."""

    ingredient_id: int
    amount: float
    unit: str


class AdaptedStep(BaseModel):
    """Một bước nấu; nhiệt độ/thời gian null khi bước không nấu (sơ chế, trộn...)."""

    step_no: int
    action: str
    temperature_c: float | None
    duration_sec: int | None


class AdaptedRecipe(BaseModel):
    """Công thức LLM trả về — lớp validation 3 kiểm tra bằng code trước khi dùng."""

    title: str
    servings: int
    ingredients: list[AdaptedIngredient]
    steps: list[AdaptedStep]


ADAPT_RECIPE_SYSTEM_PROMPT = """Bạn chỉnh một công thức nấu ăn ĐÃ KIỂM DUYỆT cho phù hợp với người dùng.

Chỉ được phép làm 3 việc:
1. Điều chỉnh khẩu phần: đổi servings theo yêu cầu và nhân/chia amount theo đúng tỉ lệ.
2. Bỏ nguyên liệu phụ (gia vị, rau thơm, đồ trang trí — không phải nguyên liệu chính) mà người dùng không có,
   và bỏ/sửa các bước chỉ dùng nguyên liệu đó.
3. Viết lại tên món và các bước bằng tiếng Việt tự nhiên, rõ ràng.

Tuyệt đối KHÔNG:
- Thêm nguyên liệu nằm ngoài danh sách nguyên liệu của công thức gốc. Chỉ dùng ingredient_id có trong công thức gốc.
- Tính hoặc nhắc tới calo, dinh dưỡng.
- Rút ngắn thời gian hoặc hạ nhiệt độ nấu ở bước có thịt, cá, hải sản, trứng:
  temperature_c và duration_sec của các bước đó phải giữ nguyên hoặc cao hơn công thức gốc.

Bước không nấu (sơ chế, trộn, bày đĩa) → temperature_c và duration_sec là null.
step_no đánh số liên tục từ 1."""
