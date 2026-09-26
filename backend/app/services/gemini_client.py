"""Client Gemini dùng chung cho vision và LLM fallback (cùng model, timeout, retry, API key)."""

from google import genai
from google.genai import types

from app.core.config import require_env

GEMINI_MODEL = "gemini-3.5-flash-lite"
REQUEST_TIMEOUT_MS = 30_000
RETRY_ATTEMPTS = 3


def create_gemini_client() -> genai.Client:
    """Client google-genai có timeout + retry; API key lấy từ GEMINI_API_KEY."""
    http_options = types.HttpOptions(
        timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=RETRY_ATTEMPTS),
    )
    return genai.Client(api_key=require_env("GEMINI_API_KEY"), http_options=http_options)
