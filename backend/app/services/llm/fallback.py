"""Chuỗi fallback LLM: thử lần lượt từng provider khi provider trước bị 429 / timeout."""

import logging

from pydantic import BaseModel

from app.services.llm.gemini_adapter import GeminiLLMAdapter
from app.services.llm.groq_adapter import GROQ_FALLBACK_MODEL, GroqAdapter
from app.services.llm.provider import LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)


class FallbackLLM(LLMProvider):
    """Gọi provider đầu tiên; chỉ chuyển sang provider kế khi LLMUnavailableError. Lỗi khác ném ra ngay."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        self._providers = providers

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        """Kết quả của provider đầu tiên trả lời được; tất cả 429/timeout → LLMUnavailableError."""
        for provider in self._providers:
            try:
                return await provider.generate_json(system_prompt, user_prompt, response_model)
            except LLMUnavailableError as error:
                logger.warning("LLM không khả dụng, thử provider kế tiếp: %s", error)
        raise LLMUnavailableError("Mọi LLM provider đều 429/timeout")


def create_recipe_llm() -> FallbackLLM:
    """gpt-oss-120b → gpt-oss-20b → Gemini (feature-spec: hết cả 3 thì pipeline trả công thức gốc)."""
    return FallbackLLM([GroqAdapter(), GroqAdapter(model=GROQ_FALLBACK_MODEL), GeminiLLMAdapter()])
