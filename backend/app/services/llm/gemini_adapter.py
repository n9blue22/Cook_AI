"""LLMProvider gọi Gemini — nấc fallback cuối trước khi trả công thức gốc."""

import httpx
from google.genai import errors, types
from pydantic import BaseModel

from app.services.gemini_client import GEMINI_MODEL, create_gemini_client
from app.services.llm.provider import LLMProvider, LLMUnavailableError
from app.services.llm.strict_schema import to_strict_json_schema

RATE_LIMIT_STATUS = 429


class GeminiLLMAdapter(LLMProvider):
    """Gemini với response_json_schema = cùng schema strict gửi Groq (không lộ field chỉ code điền)."""

    def __init__(self) -> None:
        self._client = create_gemini_client()

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        """Trả JSON thô theo schema; 429/timeout → LLMUnavailableError, response rỗng → ValueError."""
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_json_schema=to_strict_json_schema(response_model),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # không dùng tool
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=GEMINI_MODEL, contents=user_prompt, config=config,
            )
        except errors.APIError as error:
            if error.code == RATE_LIMIT_STATUS:
                raise LLMUnavailableError(f"Gemini {GEMINI_MODEL}: 429") from error
            raise
        except httpx.TimeoutException as error:
            raise LLMUnavailableError(f"Gemini {GEMINI_MODEL}: timeout") from error
        if not response.text:
            raise ValueError("Gemini trả về rỗng")
        return response.text
