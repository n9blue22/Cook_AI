from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import AsyncClient

from app.api.routes.ai import AiServices, register_ai_error_handlers
from app.api.routes.ai import router as ai_router
from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.supabase_client import create_storage_admin_client, create_supabase_client
from app.services.embedding.bge_m3 import BgeM3Provider
from app.services.image_gen.cloudflare_flux import CloudflareFluxProvider
from app.services.llm.fallback import create_recipe_llm
from app.services.vision.gemini import GeminiVisionProvider

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Tạo Supabase client + provider AI một lần khi khởi động, dùng lại qua app.state."""
    settings = get_settings()
    app.state.supabase = await create_supabase_client(settings)
    app.state.ai_services = await create_ai_services(settings, app.state.supabase)
    yield


async def create_ai_services(settings: Settings, supabase: AsyncClient) -> AiServices:
    """Provider thật cho các endpoint AI; bge-m3 nạp model (~2.2GB) ngay lúc khởi động."""
    return AiServices(
        supabase=supabase,
        storage_admin=await create_storage_admin_client(settings),
        vision=GeminiVisionProvider(),
        embedder=BgeM3Provider(),
        llm=create_recipe_llm(),
        image_gen=CloudflareFluxProvider(),
    )


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
app.include_router(ai_router, prefix=API_V1_PREFIX)
register_ai_error_handlers(app)
