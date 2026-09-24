"""Kiểm tra tình trạng các phụ thuộc bên ngoài (hiện tại: Supabase)."""

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

HEALTH_CHECK_TIMEOUT_SECONDS = 5.0
SUPABASE_AUTH_HEALTH_PATH = "/auth/v1/health"


async def is_supabase_reachable(settings: Settings) -> bool:
    """Gọi endpoint health của Supabase Auth; True nếu trả về 2xx."""
    url = settings.supabase_url.rstrip("/") + SUPABASE_AUTH_HEALTH_PATH
    headers = {"apikey": settings.supabase_publishable_key}
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as error:
        logger.warning("Không kết nối được Supabase: %s", error)
        return False
    if not response.is_success:
        logger.warning("Supabase health trả về HTTP %s", response.status_code)
    return response.is_success
