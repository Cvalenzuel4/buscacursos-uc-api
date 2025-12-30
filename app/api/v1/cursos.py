"""
Course search endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.core.logging import get_logger
from app.models.schemas import (
    APIResponse,
    BusquedaParams,
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
        logger.error(f"Error searching courses: {e}")
        
        # Check if it's a connection error to BuscaCursos
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "success": False,
                    "error": "SERVICE_UNAVAILABLE",
                    "detail": "BuscaCursos UC no está disponible en este momento. Intente más tarde.",
                },
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "INTERNAL_ERROR",
                "detail": "Error interno del servidor",
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
