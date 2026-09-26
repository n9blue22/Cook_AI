"""Interface trừu tượng cho LLM điều chỉnh công thức (bước 8 trong workflow)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMProvider(ABC):
    """Sinh text từ prompt; mỗi provider (Groq, OpenRouter...) implement lớp này."""

    @abstractmethod
    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        """Trả chuỗi JSON thô theo schema response_model; parse + validate là việc của lớp validation."""
