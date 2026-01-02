"""
Course search endpoints.
"""
import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.core.logging import get_logger
from app.models.schemas import (
    APIResponse,
    BusquedaMultipleRequest,
    BusquedaParams,
    CursoPorSigla,
    CursoSchema,
    ErrorResponse,
    VacanteDistribucion,
)
from app.services.scraper import buscar_cursos

logger = get_logger("api.cursos")

router = APIRouter(prefix="/cursos", tags=["Cursos"])


@router.get(
    "/buscar",
    response_model=APIResponse[list[CursoSchema]],
    responses={
        200: {
            "description": "Cursos encontrados exitosamente",
            "model": APIResponse[list[CursoSchema]],
        },
        400: {
            "description": "Parámetros de búsqueda inválidos",
            "model": ErrorResponse,
        },
        500: {
            "description": "Error interno del servidor",
            "model": ErrorResponse,
        },
        503: {
            "description": "BuscaCursos UC no disponible",
            "model": ErrorResponse,
        },
    },
    summary="Buscar cursos",
    description="""
Busca cursos en el catálogo de BuscaCursos UC.

**Parámetros:**
- `sigla`: Código del curso (ej: ICS2123, MAT1610)
- `semestre`: Semestre en formato YYYY-S (ej: 2025-1, 2025-2)
- `profesor`: (Opcional) Filtrar por nombre del profesor
- `campus`: (Opcional) Filtrar por campus

**Ejemplo de uso:**
```
GET /api/v1/cursos/buscar?sigla=ICS2123&semestre=2025-1
```

**Notas:**
- Los resultados se cachean por 5 minutos para evitar sobrecargar BuscaCursos UC
- La sigla es case-insensitive (se convierte a mayúsculas automáticamente)
""",
)
async def buscar_cursos_endpoint(
    sigla: Annotated[
        str,
        Query(
            description="Sigla del curso (ej: ICS2123)",
            min_length=3,
            max_length=10,
            examples=["ICS2123", "MAT1610", "FIS1503"],
        ),
    ],
    semestre: Annotated[
        str,
        Query(
            description="Semestre en formato YYYY-S",
            pattern=r"^20\d{2}-[123S]$",
            examples=["2026-1", "2025-2", "2025-3"],
        ),
    ],
    profesor: Annotated[
        str | None,
        Query(
            description="Filtrar por nombre del profesor (búsqueda parcial)",
            min_length=2,
            examples=["Pérez", "García"],
        ),
    ] = None,
    campus: Annotated[
        str | None,
        Query(
            description="Filtrar por campus",
            examples=["San Joaquín", "Casa Central"],
        ),
    ] = None,
) -> APIResponse[list[CursoSchema]]:
    """
    Search for courses in BuscaCursos UC catalog.
    """
    try:
        # Validate parameters using Pydantic model
        params = BusquedaParams(
            sigla=sigla,
            semestre=semestre,
            profesor=profesor,
            campus=campus,
        )
        
        logger.info(f"Searching courses: {params.sigla} - {params.semestre}")
        
        # Execute search
        cursos = await buscar_cursos(
            sigla=params.sigla,
            semestre=params.semestre,
            profesor=params.profesor,
            campus=params.campus,
        )
        
        return APIResponse(
            success=True,
            data=cursos,
            message=f"Se encontraron {len(cursos)} secciones" if cursos else "No se encontraron cursos",
            meta={
                "sigla": params.sigla,
                "semestre": params.semestre,
                "total_secciones": len(cursos),
            },
        )
        
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": "VALIDATION_ERROR",
                "detail": str(e),
            },
        )
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"Error searching courses: {error_type}: {error_msg}", exc_info=True)
        
        # Check if it's a connection error to BuscaCursos
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "success": False,
                    "error": "SERVICE_UNAVAILABLE",
                    "detail": "BuscaCursos UC no está disponible en este momento. Intente más tarde.",
                    "debug": f"{error_type}: {error_msg}",
                },
            )
        
        # Check if Worker is blocked
        if "captcha" in error_msg.lower() or "blocked" in error_msg.lower() or "challenge" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "success": False,
                    "error": "SCRAPER_BLOCKED",
                    "detail": "El scraper está siendo bloqueado por BuscaCursos UC.",
                    "debug": f"{error_type}: {error_msg}",
                },
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "INTERNAL_ERROR",
                "detail": "Error interno del servidor",
                "debug": f"{error_type}: {error_msg}",
            },
        )


@router.get(
    "/info/{sigla}",
    response_model=APIResponse[list[CursoSchema]],
    summary="Información de curso",
    description="Alias conveniente para buscar cursos por sigla en el semestre actual.",
)
async def get_curso_info(
    sigla: str,
    semestre: Annotated[
        str,
        Query(
            description="Semestre (default: 2026-1)",
            pattern=r"^20\d{2}-[123S]$",
        ),
    ] = "2026-1",
) -> APIResponse[list[CursoSchema]]:
    """
    Get course information by sigla (convenience endpoint).
    """
    return await buscar_cursos_endpoint(
        sigla=sigla,
        semestre=semestre,
        profesor=None,
        campus=None,
    )


@router.get(
    "/vacantes",
    response_model=APIResponse[list[VacanteDistribucion]],
    summary="Detalle de vacantes",
    description="Obtiene la distribución detallada de vacantes (reservadas, libres) para una sección específica.",
)
async def get_vacantes_endpoint(
    nrc: Annotated[str, Query(description="NRC del curso")],
    semestre: Annotated[str, Query(description="Semestre (ej: 2025-1)")] = "2026-1",
) -> APIResponse[list[VacanteDistribucion]]:
    """
    Get detailed vacancy distribution.
    """
    try:
        from app.services.scraper import get_vacantes_detalle
        from app.models.schemas import VacanteDistribucion

        detalles = await get_vacantes_detalle(nrc=nrc, semestre=semestre)
        
        return APIResponse(
            success=True,
            data=detalles,
            message="Detalle de vacantes obtenido exitosamente",
            meta={
                "nrc": nrc,
                "semestre": semestre
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching vacancies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "INTERNAL_ERROR",
                "detail": str(e),
            },
        )


@router.post(
    "/buscar-multiple",
    response_model=APIResponse[list[CursoPorSigla]],
    responses={
        200: {
            "description": "Resultados de búsqueda por sigla",
            "model": APIResponse[list[CursoPorSigla]],
        },
        400: {
            "description": "Parámetros de búsqueda inválidos",
            "model": ErrorResponse,
        },
        500: {
            "description": "Error interno del servidor",
            "model": ErrorResponse,
        },
    },
    summary="Buscar múltiples cursos",
    description="""
Busca múltiples cursos en paralelo con una sola petición.

**Ventajas:**
- Una sola petición HTTP para múltiples siglas
- Ejecución paralela: ~5 siglas toman el mismo tiempo que 1
- Resultados individuales por sigla (éxito/error separados)

**Límites:**
- Máximo 20 siglas por petición

**Ejemplo de uso:**
```json
POST /api/v1/cursos/buscar-multiple
{
  "siglas": ["ICS2123", "MAT1610", "FIS1513"],
  "semestre": "2026-1"
}
```

**Notas:**
- Cada sigla genera una petición a BuscaCursos UC (en paralelo)
- Si una sigla falla, las demás siguen funcionando
- Los resultados se cachean individualmente por 5 minutos
""",
)
async def buscar_cursos_multiple_endpoint(
    request: BusquedaMultipleRequest,
) -> APIResponse[list[CursoPorSigla]]:
    """
    Search for multiple courses in parallel using asyncio.gather.
    """
    logger.info(f"Bulk search: {len(request.siglas)} siglas - {request.semestre}")
    
    async def buscar_una_sigla(sigla: str) -> CursoPorSigla:
        """Search a single sigla and wrap the result."""
        try:
            cursos = await buscar_cursos(
                sigla=sigla,
                semestre=request.semestre,
                profesor=None,
                campus=None,
            )
            return CursoPorSigla(
                sigla=sigla,
                success=True,
                cursos=cursos,
                error=None,
            )
        except Exception as e:
            logger.warning(f"Error searching {sigla}: {e}")
            return CursoPorSigla(
                sigla=sigla,
                success=False,
                cursos=[],
                error=str(e),
            )
    
    # Execute all searches in parallel
    resultados = await asyncio.gather(
        *[buscar_una_sigla(sigla) for sigla in request.siglas]
    )
    
    # Count successes and total courses
    exitosos = sum(1 for r in resultados if r.success)
    total_cursos = sum(len(r.cursos) for r in resultados)
    
    return APIResponse(
        success=True,
        data=list(resultados),
        message=f"Búsqueda completada: {exitosos}/{len(request.siglas)} siglas exitosas, {total_cursos} secciones encontradas",
        meta={
            "semestre": request.semestre,
            "siglas_solicitadas": len(request.siglas),
            "siglas_exitosas": exitosos,
            "total_secciones": total_cursos,
        },
    )
