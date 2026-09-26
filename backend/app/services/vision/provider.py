"""Interface trừu tượng cho model vision nhận diện nguyên liệu từ ảnh."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Detected(BaseModel):
    """Nguyên liệu sống model thấy trong ảnh (tên tiếng Việt), chưa map vào bảng `ingredients`."""

    ingredients: list[str]  # nhận ra chắc chắn
    uncertain: list[str]  # thấy nhưng không chắc là gì → client hỏi lại user


class VisionUnavailableError(Exception):
    """Không nhận diện được ảnh (API lỗi / timeout / output sai schema) — user nên thử lại.

    KHÁC với ảnh không có thực phẩm (Detected rỗng): đó là kết quả hợp lệ, không phải lỗi.
    """


class VisionProvider(ABC):
    """Nhận diện nguyên liệu thô trong ảnh; mỗi provider (Gemini, Groq...) implement lớp này."""

    @abstractmethod
    async def detect_ingredients(self, image: bytes, mime_type: str) -> Detected:
        """Trả về nguyên liệu nhận ra; cả hai danh sách rỗng nếu ảnh không có thực phẩm.

        Raise VisionUnavailableError khi không nhận diện được (không trả rỗng giả).
        """
