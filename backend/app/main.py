from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import AsyncClient

from app.api.deps import limit_ip
from app.api.errors import register_common_error_handlers
from app.api.routes.ai import AiServices, register_ai_error_handlers
from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router
from app.api.routes.logs import router as logs_router
from app.api.routes.pantry import router as pantry_router
from app.api.routes.profile import router as profile_router
from app.api.routes.saved import router as saved_router
from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.http_pool import create_shared_http_client
from app.core.supabase_client import create_admin_client, create_supabase_client
from app.services.auth_service import SupabaseAuthApi
from app.services.auth_tokens import JwtVerifier
from app.services.embedding.bge_m3 import BgeM3Provider
from app.services.image_gen.cloudflare_flux import CloudflareFluxProvider
from app.services.ingredient_normalizer import IngredientCatalogCache
from app.services.llm.fallback import create_recipe_llm
from app.services.rate_limit import RateLimiter
from app.services.vision.gemini import GeminiVisionProvider

API_V1_PREFIX = "/api/v1"
SHARED_HTTP_TIMEOUT_SEC = 15.0  # mặc định cho PostgREST user; Auth/HIBP tự đặt timeout riêng theo request


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Tạo client + provider một lần khi khởi động, dùng lại qua app.state."""
    settings = get_settings()
    app.state.supabase = await create_supabase_client(settings)
    admin = await create_admin_client(settings)
    app.state.admin = admin
    app.state.catalog = IngredientCatalogCache(app.state.supabase)
    app.state.ai_services = await create_ai_services(app.state.supabase, admin, app.state.catalog)
    app.state.rate_limiter = RateLimiter(admin)
    app.state.jwt_verifier = JwtVerifier(settings.supabase_url)
    # Connection pool dùng chung cả app: Supabase Auth REST, HIBP, PostgREST bằng JWT user (deps.user_db_dependency).
    # KHÔNG đặt header mặc định nào (nhất là Authorization) — token luôn gắn theo từng request.
    async with create_shared_http_client(SHARED_HTTP_TIMEOUT_SEC) as http:
        app.state.http = http
        app.state.auth_api = SupabaseAuthApi(settings.supabase_url, settings.supabase_publishable_key, http)
        yield


async def create_ai_services(supabase: AsyncClient, admin: AsyncClient, catalog: IngredientCatalogCache) -> AiServices:
    """Provider thật cho các endpoint AI; bge-m3 nạp model (~2.2GB) ngay lúc khởi động."""
    return AiServices(
        supabase=supabase,
        admin=admin,
        vision=GeminiVisionProvider(),
        embedder=BgeM3Provider(),
        llm=create_recipe_llm(),
        image_gen=CloudflareFluxProvider(),
        catalog=catalog,
    )


def create_app(settings: Settings) -> FastAPI:
    """FastAPI app: CORS theo domain cụ thể (có cookie), router, handler lỗi."""
    application = FastAPI(title="Bếp AI API", description="FastAPI backend cho app Bếp AI", version="1.0.0", lifespan=lifespan)
    # Có cookie (refresh token web) → không được dùng "*"; chỉ các domain frontend trong CORS_ORIGINS.
    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After"],  # web đọc được số giây chờ khi 429 (mặc định trình duyệt giấu header này)
    )
    application.include_router(health_router, prefix=API_V1_PREFIX, dependencies=[Depends(limit_ip("default_ip"))])
    application.include_router(auth_router, prefix=API_V1_PREFIX)
    for user_data_router in (profile_router, pantry_router, logs_router, saved_router):
        application.include_router(user_data_router, prefix=API_V1_PREFIX)
    application.include_router(ai_router, prefix=API_V1_PREFIX)
    register_common_error_handlers(application)
    register_ai_error_handlers(application)
    return application


app = create_app(get_settings())
