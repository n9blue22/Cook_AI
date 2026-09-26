"""Khởi tạo Supabase client dùng chung cho backend."""

from supabase import AsyncClient, acreate_client

from app.core.config import Settings


async def create_supabase_client(settings: Settings) -> AsyncClient:
    """Tạo async Supabase client từ URL + publishable key trong Settings."""
    return await acreate_client(settings.supabase_url, settings.supabase_publishable_key)


async def create_storage_admin_client(settings: Settings) -> AsyncClient:
    """Client secret key (bỏ qua RLS) — CHỈ dùng ghi Storage; đọc dữ liệu vẫn qua client publishable."""
    return await acreate_client(settings.supabase_url, settings.supabase_secret_key)
