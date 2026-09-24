from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.supabase_client import create_supabase_client

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Tạo Supabase client một lần khi khởi động, dùng lại qua app.state."""
    app.state.supabase = await create_supabase_client(get_settings())
    yield


app = FastAPI(
    title="Bếp AI API",
    description="FastAPI backend cho app Bếp AI",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS cho app React Native (mobile & web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production: thay bằng domain cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=API_V1_PREFIX)
