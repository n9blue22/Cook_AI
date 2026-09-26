"""Test gọi Gemini thật — cần GEMINI_API_KEY trong backend/.env, không có thì skip.

Ảnh mẫu (tests/fixtures/, Wikimedia Commons):
- chicken_parmesan_mise_en_place.jpg — Balise42, CC BY-SA 4.0,
  https://commons.wikimedia.org/wiki/File:Chicken_parmesan_mise_en_place.jpg
  (ức gà sống, mozzarella, trứng đánh, bột mì, vụn bánh mì, sốt cà chua)
- keyboard_keys.jpg — John Snyder, CC BY-SA 4.0,
  https://commons.wikimedia.org/wiki/File:Closeup_of_keys.jpg
  (bàn phím, không có thực phẩm)

TODO: Chưa có ảnh mẫu test case uncertain có phần tử — bổ sung nếu cần khi tích hợp thật ở Lệnh 6.
"""

import asyncio
import os
from pathlib import Path

import pytest

from app.services.vision.gemini import GeminiVisionProvider  # import này nạp backend/.env trước skipif
from app.services.vision.provider import Detected

FIXTURES_DIR = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="cần GEMINI_API_KEY để gọi Gemini thật")


def detect_fixture(file_name: str) -> Detected:
    """Gửi một ảnh trong fixtures/ cho Gemini, in kết quả để xem khi chạy pytest -s."""
    image = (FIXTURES_DIR / file_name).read_bytes()
    detected = asyncio.run(GeminiVisionProvider().detect_ingredients(image, "image/jpeg"))
    print(file_name, detected)
    return detected


def test_detects_raw_chicken_without_guessing_dish_name() -> None:
    detected = detect_fixture("chicken_parmesan_mise_en_place.jpg")

    assert any("gà" in name for name in detected.ingredients)
    all_names = [name.lower() for name in detected.ingredients + detected.uncertain]
    assert not any("gà parmesan" in name or "parmigiana" in name for name in all_names)  # không đoán tên món


def test_non_food_image_returns_no_ingredients() -> None:
    detected = detect_fixture("keyboard_keys.jpg")

    assert detected.ingredients == []
    assert detected.uncertain == []
