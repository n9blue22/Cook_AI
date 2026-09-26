"""Interface trừu tượng cho LLM điều chỉnh công thức (bước 8 trong workflow)."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Sinh text từ prompt; mỗi provider (Groq, OpenRouter...) implement lớp này."""

    @abstractmethod
    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """Trả về chuỗi JSON thô; parse và validate là việc của lớp validation, không phải provider."""
