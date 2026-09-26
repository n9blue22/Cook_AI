"""VisionProvider dùng Gemini (google-genai SDK), ép output JSON theo schema Detected."""

from google import genai
from google.genai import types

from app.core.config import require_env
from app.services.vision.provider import Detected, VisionProvider

GEMINI_MODEL = "gemini-3.5-flash-lite"
REQUEST_TIMEOUT_MS = 30_000
RETRY_ATTEMPTS = 3

SYSTEM_PROMPT = """Bạn nhận diện NGUYÊN LIỆU SỐNG trong ảnh để gợi ý món nấu.
- Chỉ liệt kê nguyên liệu thực phẩm chưa nấu mà bạn NHÌN THẤY trong ảnh (thịt, cá, trứng, rau, củ, quả, gia vị...).
- Tên tiếng Việt, ngắn gọn, viết thường, không kèm số lượng (ví dụ: "ức gà", "cà chua", "trứng gà").
- KHÔNG đoán tên món ăn. KHÔNG suy ra nguyên liệu không nhìn thấy.
- "ingredients": nguyên liệu nhận ra chắc chắn.
- "uncertain": thấy có nguyên liệu nhưng không chắc là gì (ví dụ bột trắng không rõ bột mì hay bột năng).
- Mỗi nguyên liệu chỉ nằm ở một danh sách.
- Ảnh không có thực phẩm nào → cả hai danh sách rỗng. Không bịa."""

USER_PROMPT = "Liệt kê nguyên liệu sống trong ảnh này."


class GeminiVisionProvider(VisionProvider):
    """Gọi Gemini với temperature 0 và response_schema=Detected; API key lấy từ GEMINI_API_KEY."""

    def __init__(self) -> None:
        http_options = types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=RETRY_ATTEMPTS),
        )
        self._client = genai.Client(api_key=require_env("GEMINI_API_KEY"), http_options=http_options)
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0,
            response_mime_type="application/json",
            response_schema=Detected,
        )

    async def detect_ingredients(self, image: bytes, mime_type: str) -> Detected:
        """Gửi ảnh cho Gemini.

        Raise ValueError (sai schema), genai.errors.APIError hoặc timeout — người gọi phải bắt, xem feature-spec mục 7.
        """
        response = await self._client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Part.from_bytes(data=image, mime_type=mime_type), USER_PROMPT],
            config=self._config,
        )
        if not isinstance(response.parsed, Detected):
            raise ValueError(f"Gemini trả về không đúng schema Detected: {response.text!r}")
        return response.parsed
