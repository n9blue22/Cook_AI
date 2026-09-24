from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.health_service import is_supabase_reachable

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    supabase: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Trạng thái backend và kết nối Supabase."""
    settings = get_settings()
    supabase_ok = await is_supabase_reachable(settings)
    return HealthResponse(
        status="ok" if supabase_ok else "degraded",
        environment=settings.environment,
        supabase="ok" if supabase_ok else "unreachable",
    )
