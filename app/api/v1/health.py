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
    from app.services.http_client import get_page_content
    from app.core.config import get_settings
    
    settings = get_settings()
    url = "https://buscacursos.uc.cl/"
    
    try:
        html = await get_page_content(url, {})
        return {
            "success": True if html else False,
            "url": url,
            "content_length": len(html) if html else 0
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
    Full diagnostic endpoint - does a real course search.
    """
    from app.services.http_client import get_page_content
    from app.services.scraper import parse_html_to_courses
    
    results = {
        "strategy": "ScrapingAnt (Prod) or curl_cffi (Dev)",
        "tests": {}
    }
    
    # Test: Real search
    try:
        url_target = "https://buscacursos.uc.cl/"
        params = {
            'cxml_semestre': '2026-1',
            'cxml_sigla': 'MAT1610',
            'cxml_horario_tipo_busqueda': 'si_tenga',
            'cxml_horario_tipo_busqueda_actividad': 'TODOS',
        }
        
        html = await get_page_content(url_target, params)
        cursos = parse_html_to_courses(html)
        
        results["tests"]["search"] = {
            "success": True,
            "response_length": len(html),
            "courses_found": len(cursos),
            "sample_course": cursos[0].nombre if cursos else None,
        }
    except Exception as e:
        results["tests"]["search"] = {
            "success": False,
            "error_type": type(e).__name__,
            "error": str(e),
        }
    
    # Overall status
    results["overall_healthy"] = all(
        t.get("success", False) for t in results["tests"].values()
    )
    
    return results
