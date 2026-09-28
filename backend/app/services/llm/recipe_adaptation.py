"""Schema output và system prompt cho bước LLM điều chỉnh công thức (feature-spec mục 4 bước [8], mục 5 lớp 3)."""

from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema


class AdaptedIngredient(BaseModel):
    """Một nguyên liệu trong công thức đã chỉnh; ingredient_id phải lấy từ công thức gốc."""

    ingredient_id: int
    amount: float | None  # null khi công thức gốc không ghi lượng (toàn bộ Food.com)
    unit: str | None


class AdaptedStep(BaseModel):
    """Một bước nấu; nhiệt độ/thời gian null khi bước không nấu (sơ chế, trộn...)."""

    step_no: int
    action: str
    temperature_c: float | None
    duration_sec: int | None


class AdaptedRecipe(BaseModel):
    """Công thức LLM đã chỉnh (từ LLMAdaptedRecipe.to_adapted) — lớp validation 3 kiểm tra bằng code trước khi dùng."""

    title: str
    servings: int
    ingredients: list[AdaptedIngredient]
    steps: list[AdaptedStep]
    # Không nằm trong schema gửi LLM (to_strict_json_schema): code điền từ food_safety.rest_sec
    # sau khi validate (with_rest_time).
    # UI hiển thị "để thịt nghỉ N phút trước khi cắt"; 0 = không cần nghỉ.
    rest_sec: SkipJsonSchema[int] = 0


class LLMAdaptedStep(BaseModel):
    """Bước LLM trả: tách nhiệt độ lõi (kiểm tra an toàn) khỏi nhiệt độ lò/dầu/bếp — gpt-oss hay ghi 180°C của lò
    vào ô lõi (đo 2026-09-28). heat_setting_c chỉ là chỗ để model ghi đúng ô, không validate, không trả client."""

    step_no: int
    action: str
    heat_setting_c: float | None
    core_temp_c: float | None
    duration_sec: int | None

    def to_step(self) -> AdaptedStep:
        """Bước trả client/validation: temperature_c chỉ lấy từ core_temp_c."""
        return AdaptedStep(
            step_no=self.step_no, action=self.action, temperature_c=self.core_temp_c, duration_sec=self.duration_sec,
        )


class LLMAdaptedRecipe(BaseModel):
    """Schema gửi LLM; to_adapted() đổi về AdaptedRecipe (API + công thức đã lưu giữ nguyên dạng temperature_c)."""

    title: str
    servings: int
    ingredients: list[AdaptedIngredient]
    steps: list[LLMAdaptedStep]

    def to_adapted(self) -> AdaptedRecipe:
        """Bỏ heat_setting_c, core_temp_c → temperature_c."""
        return AdaptedRecipe(
            title=self.title, servings=self.servings, ingredients=self.ingredients,
            steps=[step.to_step() for step in self.steps],
        )


ADAPT_RECIPE_SYSTEM_PROMPT = """Bạn chỉnh một công thức nấu ăn ĐÃ KIỂM DUYỆT cho phù hợp với người dùng.

Chỉ được phép làm 3 việc:
1. Điều chỉnh khẩu phần: đổi servings theo yêu cầu và nhân/chia amount theo đúng tỉ lệ.
2. Bỏ nguyên liệu phụ (gia vị, rau thơm, đồ trang trí — không phải nguyên liệu chính) mà người dùng không có,
   và bỏ/sửa các bước chỉ dùng nguyên liệu đó.
   Gia vị cơ bản (muối, tiêu, đường, nước mắm, hạt nêm, bột ngọt, dầu ăn, nước) LUÔN coi là có sẵn trong bếp —
   KHÔNG được xoá các bước nêm nếm/sử dụng gia vị này khỏi công thức, dù user không liệt kê chúng trong danh sách
   nguyên liệu đang có. Chỉ bỏ nguyên liệu KHÔNG thuộc nhóm gia vị cơ bản mà user thật sự không có.
3. Viết lại tên món và các bước bằng tiếng Việt tự nhiên, rõ ràng.

Tuyệt đối KHÔNG:
- Thêm nguyên liệu nằm ngoài danh sách nguyên liệu của công thức gốc. Chỉ dùng ingredient_id có trong công thức gốc.
- Tính hoặc nhắc tới calo, dinh dưỡng.
- Rút ngắn thời gian hoặc hạ nhiệt độ nấu ở bước có thịt, cá, hải sản, trứng:
  core_temp_c và duration_sec của các bước đó phải giữ nguyên hoặc cao hơn công thức gốc.

Nhiệt độ và thời gian — mỗi bước có 2 ô nhiệt độ KHÁC NHAU:
- heat_setting_c = nhiệt độ lò / dầu / nước / bếp dùng để nấu (vd nướng 180°C, chiên dầu 170°C, luộc 100°C).
  Không biết thì null.
- core_temp_c = nhiệt độ LÕI thực phẩm khi chín (gà/vịt 75°C, thịt xay và trứng 71°C, thịt heo/bò miếng và cá 63°C), luôn ≤ 100°C.
  CHỈ điền khi action nói rõ "đến khi lõi đạt X°C" và X = core_temp_c. Không bao giờ ghi nhiệt độ lò/dầu vào đây.
- Bước đun nấu thịt, cá, hải sản, trứng PHẢI có action ghi "đến khi lõi đạt X°C", core_temp_c = X và
  duration_sec = thời gian nấu, kể cả khi công thức gốc để trống.
- Bước đun nấu khác (rau, nước dùng...): heat_setting_c + duration_sec, core_temp_c có thể null.
- Bước không đun nấu (sơ chế, ướp, trộn, ngâm, bày đĩa) → cả heat_setting_c, core_temp_c, duration_sec là null.

Nguyên liệu công thức gốc không ghi lượng (amount null) → giữ amount và unit là null, không tự bịa lượng.
step_no đánh số liên tục từ 1."""
