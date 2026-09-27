"""Cấu hình ứng dụng, đọc từ biến môi trường (file backend/.env khi chạy local)."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEV_FRONTEND_URL = "http://localhost:8081"  # expo start --web
load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    environment: str
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str  # chỉ dùng phía server (Storage, RPC nội bộ), không bao giờ trả ra client
    cors_origins: tuple[str, ...]  # domain frontend được gọi API kèm cookie — không dùng "*"
    frontend_url: str  # đích redirect của link xác minh email / đặt lại mật khẩu


def require_env(name: str) -> str:
    """Đọc biến môi trường bắt buộc, báo lỗi rõ ràng nếu thiếu."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Thiếu biến môi trường {name} — xem backend/.env.example")
    return value


@lru_cache
def get_settings() -> Settings:
    """Trả về Settings dùng chung cho toàn app (đọc env một lần)."""
    return Settings(
        environment=os.getenv("ENV", "development"),
        supabase_url=require_env("SUPABASE_URL"),
        supabase_publishable_key=require_env("SUPABASE_PUBLISHABLE_KEY"),
        supabase_secret_key=require_env("SUPABASE_SECRET_KEY"),
        cors_origins=tuple(o.strip() for o in os.getenv("CORS_ORIGINS", DEV_FRONTEND_URL).split(",") if o.strip()),
        frontend_url=os.getenv("FRONTEND_URL", DEV_FRONTEND_URL).rstrip("/"),
    )
