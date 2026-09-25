"""Cấu hình ứng dụng, đọc từ biến môi trường (file backend/.env khi chạy local)."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    environment: str
    supabase_url: str
    supabase_publishable_key: str


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
    )
