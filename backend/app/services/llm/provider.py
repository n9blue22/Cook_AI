"""Interface trừu tượng cho LLM điều chỉnh công thức (bước 8 trong workflow)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMUnavailableError(Exception):
    """Provider tạm không phục vụ được (429 rate limit / timeout) — nên thử provider kế tiếp."""


class LLMProvider(ABC):
    """Sinh text từ prompt; mỗi provider (Groq, Gemini...) implement lớp này."""

    @abstractmethod
    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        """Trả chuỗi JSON thô theo schema response_model; parse + validate là việc của lớp validation.

        Raise LLMUnavailableError khi bị 429 hoặc timeout; lỗi khác để nguyên cho người gọi xử lý.
        """
