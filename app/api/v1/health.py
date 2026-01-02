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


@router.get(
    "/health/scrape-test",
    summary="Prueba de conectividad de scraping",
    description="Intenta conectar a Buscacursos y devuelve el estado HTTP. Útil para diagnosticar bloqueos (403).",
)
async def scrape_test_endpoint():
    """
    Diagnostic endpoint to check if Render IP is blocked.
    """
    from app.services.http_client import get_http_client
    
    client = get_http_client()
    url = "https://buscacursos.uc.cl/"
    
    try:
        # Use fetch method which is a simple GET
        response = await client.fetch(url)
        return {
            "success": True,
            "status_code": response.status_code,
            "url": url,
            "headers": dict(response.headers),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "detail": "Failed to connect to Buscacursos. Likely IP block or timeout.",
        }


@router.get(
    "/health/full-test",
    summary="Prueba completa de scraping",
    description="Realiza una búsqueda real de cursos para verificar que todo el flujo funciona.",
)
async def full_scrape_test():
    """
    Full diagnostic endpoint - does a real course search using curl_cffi.
    """
    from app.services.http_client import get_http_client
    from app.services.scraper import parse_html_to_courses
    from app.core.config import get_settings
    
    settings = get_settings()
    results = {
        "environment": settings.environment,
        "strategy": "curl_cffi direct (no external proxy)",
        "tests": {}
    }
    
    client = get_http_client()
    
    # Test: Direct curl_cffi connection with browser impersonation
    try:
        response = await client.search_courses(
            semestre="2025-1",
            sigla="MAT1610"
        )
        cursos = parse_html_to_courses(response.text)
        results["tests"]["direct_scrape"] = {
            "success": True,
            "status_code": response.status_code,
            "response_length": len(response.text),
            "courses_found": len(cursos),
            "sample_course": cursos[0].nombre if cursos else None,
        }
    except Exception as e:
        results["tests"]["direct_scrape"] = {
            "success": False,
            "error_type": type(e).__name__,
            "error": str(e),
        }
    
    # Overall status
    results["overall_healthy"] = all(
        t.get("success", False) for t in results["tests"].values()
    )
    
    return results
