"""Supabase client dùng secret key cho các script seed (bỏ qua RLS, không dùng trong app)."""

from supabase import Client, create_client

from app.core.config import require_env


def create_admin_client() -> Client:
    """Tạo client ghi được bảng danh mục; cần SUPABASE_URL và SUPABASE_SECRET_KEY trong backend/.env."""
    return create_client(require_env("SUPABASE_URL"), require_env("SUPABASE_SECRET_KEY"))
