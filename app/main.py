"""
BuscaCursos UC API - Main Application Entry Point

A production-ready RESTful API for scraping course data from BuscaCursos UC.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import cursos, health
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.http_client import close_http_client

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Cache TTL: {settings.cache_ttl_seconds}s")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_http_client()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="""
## BuscaCursos UC API

API RESTful para obtener información de cursos desde el catálogo de BuscaCursos UC.

### Características

- 🔍 **Búsqueda de cursos** por sigla, semestre, profesor y campus
- 📅 **Horarios estructurados** con tipo, día, módulos y sala
- ⚡ **Caché inteligente** para evitar peticiones repetidas
- 🔄 **Reintentos automáticos** con backoff exponencial
- 🛡️ **Anti-bloqueo** con rotación de User-Agent

### Uso

```bash
# Buscar un curso
curl "https://tu-api.com/api/v1/cursos/buscar?sigla=ICS2123&semestre=2025-1"
```

### Límites

- Los resultados se cachean por 5 minutos
- Máximo de reintentos: 3 por petición

### Desarrollador

Proyecto open-source para la comunidad UC.
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(cursos.router, prefix="/api/v1")
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "INTERNAL_ERROR",
                "detail": "An unexpected error occurred",
            },
        )
    
    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect to API documentation."""
        return {
            "message": "BuscaCursos UC API",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
    
    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
