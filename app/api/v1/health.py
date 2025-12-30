"""
Health check and utility endpoints.
"""
from fastapi import APIRouter

from app.core.cache import clear_cache, get_cache_stats
from app.core.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica el estado del servicio y la configuración de caché.",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns service status and cache statistics.
    """
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        cache_stats=get_cache_stats(),
    )


@router.post(
    "/cache/clear",
    summary="Limpiar caché",
    description="Limpia la caché de resultados. Útil para forzar actualización de datos.",
)
async def clear_cache_endpoint() -> dict:
    """
    Clear the cache.
    """
    count = clear_cache()
    return {
        "success": True,
        "message": f"Cache cleared: {count} entries removed",
    }
