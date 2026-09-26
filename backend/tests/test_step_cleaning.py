"""Test dọn bước cuối — các câu lấy từ dữ liệu thật."""

import pytest

from scripts.step_cleaning import clean_final_step, clean_steps

LAU_TOM_PROMO = (
    "Tiết trời se lạnh là thời điểm vàng cho các món lẩu lên ngôi. Còn gì tuyệt vời hơn khi cả nhà cùng quây quần "
    "bên nhau và thưởng thức món lẩu tôm càng thơm ngon này chứ. Hãy cùng chúng tôi trổ tài nấu ăn ngon và chế biến "
    "món lẩu tôm cho cả gia đình thưởng thức nhé"
)


@pytest.mark.parametrize("step", [
    LAU_TOM_PROMO,
    "this recipe yields 1 3 / 4 cups",
    "Chúc bạn thành công!",
    "Enjoy!",
])
def test_promo_only_final_step_is_removed(step: str) -> None:
    assert clean_final_step(step) is None


def test_trailing_promo_sentence_is_trimmed_but_instruction_kept() -> None:
    assert clean_final_step("Cho hành lá vào, tắt bếp. Chúc bạn thành công!") == "Cho hành lá vào, tắt bếp."


def test_bao_tu_ca_keeps_instruction_drops_xin_moi() -> None:
    assert clean_final_step("Cho bao tử cá ba sa xào bơ ra dĩa. Xin mời") == "Cho bao tử cá ba sa xào bơ ra dĩa."


@pytest.mark.parametrize("step", [
    "Múc ra tô, rắc tiêu và thưởng thức khi còn nóng.",
    "place butter in bottom of deep bowl , pour in pan roast , sprinkle with paprika and serve",
    "bake at 375 for 10-15 minutes",
])
def test_real_final_instruction_is_untouched(step: str) -> None:
    assert clean_final_step(step) == step


def test_only_last_step_is_touched() -> None:
    steps = ["Xin mời chuẩn bị nguyên liệu.", "Cho thịt vào xào.", "Chúc bạn thành công!"]
    assert clean_steps(steps) == ["Xin mời chuẩn bị nguyên liệu.", "Cho thịt vào xào."]


def test_single_step_recipe_is_never_emptied() -> None:
    assert clean_steps(["Chúc bạn thành công!"]) == ["Chúc bạn thành công!"]


@pytest.mark.parametrize("step", [
    "baked until heated through , about 15-20 minutes",
    "continue baking until crisp and browned",
    "for a little extra crispness , finish cooking the fries under the broiler",
    "salt and pepper to taste",
])
def test_inflected_english_instructions_are_kept(step: str) -> None:
    assert clean_final_step(step) == step


@pytest.mark.parametrize("step", [
    "dust with powdered sugar before serving",
    "separate sauce into equal parts",
    "crumble bacon over pasta",
    "process cauliflower and other ingredients in food processor",
    "pat them dry before putting them on your sandwich",
    "Rau củ chín tắt lửa.",
    "Thực hiện tương tự với cá cơm.",
])
def test_more_real_instructions_are_kept(step: str) -> None:
    assert clean_final_step(step) == step


def test_missing_space_before_promo_sentence_is_split() -> None:
    step = "Khi ăn chấm cùng tương ớt và tương cà chua.Chúc các bạn thành công"
    assert clean_final_step(step) == "Khi ăn chấm cùng tương ớt và tương cà chua."


@pytest.mark.parametrize(("step", "expected"), [
    ("Tạo hình mặt con thỏ với cà chua làm mắt, thịt cua làm mũi và đậu hũ làm răng thỏ",
     "Tạo hình mặt con thỏ với cà chua làm mắt, thịt cua làm mũi và đậu hũ làm răng thỏ"),
    ("Để bánh nguội trên khay, không di chuyển khi bánh còn nóng vì sẽ làm vỡ bánh.",
     "Để bánh nguội trên khay, không di chuyển khi bánh còn nóng vì sẽ làm vỡ bánh."),
    ("Trình bày: dọn món ăn ra đĩa, dùng với cơm nóng, chúc bạn ngon miệng.",
     "Trình bày: dọn món ăn ra đĩa, dùng với cơm nóng"),
])
def test_vietnamese_serving_and_shaping_steps_are_kept(step: str, expected: str) -> None:
    assert clean_final_step(step) == expected


@pytest.mark.parametrize("step", [
    "fish should flake easily when done",
    "snapper is done when it flakes easily with a fork",
    "be careful not to overcook the fish",
    "make sure the oil is hot enough",
    "the cake is ready when a toothpick comes out clean",
    "it should just be slightly warmed and retain it's crunch",
])
def test_doneness_and_caution_cues_are_kept(step: str) -> None:
    assert clean_final_step(step) == step


def test_promo_still_removed_next_to_cue() -> None:
    assert clean_final_step("fish should flake easily. Enjoy!") == "fish should flake easily."


@pytest.mark.parametrize("step", [
    "don't overcook them , though",
    "35 minute depending on thickness of salmon",
    "the big challenge here is not overcooking the fillets- 8 minutes will do for thin fillets",
])
def test_timing_and_overcook_cues_are_kept(step: str) -> None:
    assert clean_final_step(step) == step


@pytest.mark.parametrize("step", [
    "it takes at least an hour for this to come to room temperature after being in the fridge",
    "the eggs will be broken up when then are done",
    "if the reaction is at all delayed or weak , throw it away and buy a fresh can",
])
def test_hour_done_and_throw_cues_are_kept(step: str) -> None:
    assert clean_final_step(step) == step
