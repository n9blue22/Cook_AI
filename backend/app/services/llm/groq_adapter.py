"""LLMProvider gọi Groq qua openai SDK, ép output bằng json_schema strict."""

from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.core.config import require_env
from app.services.llm.provider import LLMProvider, LLMUnavailableError
from app.services.llm.strict_schema import to_strict_json_schema

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODEL = "openai/gpt-oss-20b"  # nhỏ hơn, hạn mức rate limit riêng — dùng khi 120b bị 429/timeout
REQUEST_TIMEOUT_SEC = 60.0
MAX_RETRIES = 3
COMPLETE_FINISH_REASON = "stop"


class GroqAdapter(LLMProvider):
    """Groq chat completions; API key lấy từ GROQ_API_KEY."""

    def __init__(self, model: str = GROQ_MODEL) -> None:
        self.model = model
        self._client = AsyncOpenAI(
            base_url=GROQ_BASE_URL,
            api_key=require_env("GROQ_API_KEY"),
            timeout=REQUEST_TIMEOUT_SEC,
            max_retries=MAX_RETRIES,
        )

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        """Trả JSON thô đúng schema response_model; 429/timeout (sau retry) → LLMUnavailableError."""
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": to_strict_json_schema(response_model),
                    },
                },
            )
        except (RateLimitError, APITimeoutError) as error:
            raise LLMUnavailableError(f"Groq {self.model}: {type(error).__name__}") from error
        choice = response.choices[0]
        if choice.finish_reason != COMPLETE_FINISH_REASON or not choice.message.content:
            raise ValueError(f"Groq trả về không trọn vẹn (finish_reason={choice.finish_reason!r})")
        return choice.message.content
