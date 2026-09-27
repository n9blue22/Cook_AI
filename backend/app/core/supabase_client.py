"""Khởi tạo Supabase client dùng chung cho backend."""

from supabase import AsyncClient, acreate_client

from app.core.config import Settings


async def create_supabase_client(settings: Settings) -> AsyncClient:
    """Tạo async Supabase client từ URL + publishable key trong Settings."""
    return await acreate_client(settings.supabase_url, settings.supabase_publishable_key)


async def create_admin_client(settings: Settings) -> AsyncClient:
    """Client secret key (bỏ qua RLS) — CHỈ cho việc nội bộ server: ghi Storage, RPC search_recipes /
    consume_daily_quota. Dữ liệu của user luôn đọc/ghi bằng JWT của chính user (auth_tokens.user_db)."""
    return await acreate_client(settings.supabase_url, settings.supabase_secret_key)
