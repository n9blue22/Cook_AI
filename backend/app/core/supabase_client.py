"""Khởi tạo Supabase client dùng chung cho backend."""

from postgrest.constants import DEFAULT_POSTGREST_CLIENT_TIMEOUT
from supabase import AsyncClient, AsyncClientOptions, acreate_client

from app.core.config import Settings
from app.core.http_pool import create_shared_http_client


async def create_supabase_client(settings: Settings) -> AsyncClient:
    """Tạo async Supabase client từ URL + publishable key trong Settings, đi qua pool dùng chung (http_pool)."""
    # timeout + HTTP/2 giữ như client mặc định postgrest dựng khi không truyền httpx_client
    http = create_shared_http_client(DEFAULT_POSTGREST_CLIENT_TIMEOUT, http2=True)
    options = AsyncClientOptions(httpx_client=http)
    return await acreate_client(settings.supabase_url, settings.supabase_publishable_key, options)


async def create_admin_client(settings: Settings) -> AsyncClient:
    """Client secret key (bỏ qua RLS) — CHỈ cho việc nội bộ server: ghi Storage, RPC search_recipes /
    consume_daily_quota. Dữ liệu của user luôn đọc/ghi bằng JWT của chính user (auth_tokens.user_db)."""
    return await acreate_client(settings.supabase_url, settings.supabase_secret_key)
