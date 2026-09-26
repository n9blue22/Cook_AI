"""Interface trừu tượng cho model sinh ảnh minh hoạ món ăn (tính năng lazy, P1)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedImage:
    """Ảnh do AI dựng, sẵn sàng lưu vào Supabase Storage."""

    content: bytes
    mime_type: str


class ImageGenProvider(ABC):
    """Sinh ảnh từ mô tả món; mỗi provider implement lớp này."""

    @abstractmethod
    async def generate_image(self, prompt: str) -> GeneratedImage:
        """Trả về một ảnh minh hoạ cho prompt."""
