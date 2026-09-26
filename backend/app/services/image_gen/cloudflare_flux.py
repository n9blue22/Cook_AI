"""ImageGenProvider gọi Cloudflare Workers AI, model FLUX.1 [schnell] (4 bước khử nhiễu)."""

import asyncio
import base64

import httpx

from app.core.config import require_env
from app.services.image_gen.provider import GeneratedImage, ImageGenProvider, ImageGenUnavailableError

FLUX_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
FLUX_STEPS = 4
FLUX_IMAGE_MIME = "image/jpeg"  # model trả base64 JPEG
REQUEST_TIMEOUT_SEC = 60.0
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SEC = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
ERROR_BODY_PREVIEW_CHARS = 300


class CloudflareFluxProvider(ImageGenProvider):
    """API key lấy từ CF_ACCOUNT_ID + CF_API_TOKEN; retry khi 429/5xx/timeout."""

    def __init__(self) -> None:
        self._url = FLUX_URL.format(account_id=require_env("CF_ACCOUNT_ID"))
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {require_env('CF_API_TOKEN')}"}, timeout=REQUEST_TIMEOUT_SEC,
        )

    async def generate_image(self, prompt: str) -> GeneratedImage:
        """Ảnh JPEG cho prompt; mọi lỗi (sau retry) → ImageGenUnavailableError."""
        response = await self._post_with_retry({"prompt": prompt, "steps": FLUX_STEPS})
        image_base64 = (response.json().get("result") or {}).get("image")
        if not image_base64:
            raise ImageGenUnavailableError(f"FLUX không trả ảnh: {response.text[:ERROR_BODY_PREVIEW_CHARS]}")
        return GeneratedImage(content=base64.b64decode(image_base64), mime_type=FLUX_IMAGE_MIME)

    async def _post_with_retry(self, body: dict) -> httpx.Response:
        """POST; 429/5xx/lỗi mạng thì thử lại có backoff, lỗi khác (sai token, prompt bị chặn) ném ngay."""
        last_error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await self._client.post(self._url, json=body)
            except httpx.TransportError as error:  # gồm cả timeout
                last_error = f"{type(error).__name__}: {error}"
            else:
                if response.is_success:
                    return response
                last_error = f"HTTP {response.status_code}: {response.text[:ERROR_BODY_PREVIEW_CHARS]}"
                if response.status_code not in RETRYABLE_STATUS:
                    break
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_BACKOFF_SEC * attempt)
        raise ImageGenUnavailableError(f"Cloudflare FLUX lỗi: {last_error}")
