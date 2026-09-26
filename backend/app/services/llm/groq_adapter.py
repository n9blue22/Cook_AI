"""LLMProvider gọi Groq qua openai SDK, ép output bằng json_schema strict."""

from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import require_env
from app.services.llm.provider import LLMProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"
REQUEST_TIMEOUT_SEC = 60.0
MAX_RETRIES = 3
COMPLETE_FINISH_REASON = "stop"


def to_groq_strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema của Pydantic → dạng Groq strict: inline $ref, mọi object additionalProperties=false + required đủ."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def strictify(node: Any) -> Any:
        if isinstance(node, list):
            return [strictify(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return strictify(definitions[node["$ref"].removeprefix("#/$defs/")])
        node = {key: strictify(value) for key, value in node.items()}
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        return node

    return strictify(schema)


class GroqAdapter(LLMProvider):
    """Groq model gpt-oss-120b; API key lấy từ GROQ_API_KEY."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=GROQ_BASE_URL,
            api_key=require_env("GROQ_API_KEY"),
            timeout=REQUEST_TIMEOUT_SEC,
            max_retries=MAX_RETRIES,
        )

    async def generate_json(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel]) -> str:
        """Trả JSON thô đúng schema response_model; raise ValueError nếu model không trả hết câu trả lời."""
        response = await self._client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": to_groq_strict_schema(response_model),
                },
            },
        )
        choice = response.choices[0]
        if choice.finish_reason != COMPLETE_FINISH_REASON or not choice.message.content:
            raise ValueError(f"Groq trả về không trọn vẹn (finish_reason={choice.finish_reason!r})")
        return choice.message.content
