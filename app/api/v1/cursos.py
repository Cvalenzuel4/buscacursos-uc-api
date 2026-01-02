from fastapi import APIRouter, HTTPException, Query
from app.services.http_client import get_page_content
from app.services.scraper import parse_html_to_courses
from app.models.schemas import (
    SearchResponse, 
    CursoSchema, 
    VacanteDistribucion, 
    BusquedaMultipleRequest, 
    CursoPorSigla,
    APIResponse
)
from cachetools import TTLCache
import asyncio
import urllib.parse

router = APIRouter(prefix="/cursos", tags=["Cursos"])

# Caché en memoria RAM (Se reinicia si el servidor se apaga)
# TTL = 3600 segundos (1 hora).
# Si un dato expira, NO se recarga automáticamente. Se espera a que un usuario lo pida.
cache = TTLCache(maxsize=1000, ttl=3600)

async def _buscar_curso_logic(sigla: str, semestre: str) -> SearchResponse:
    """
    Logic for searching a single course with cache.
    """
    # Validar y normalizar sigla
    sigla = sigla.strip().upper()
    cache_key = f"{semestre}_{sigla}"
    
    # 1. Intento de Caché (Gratis)
    if cache_key in cache:
        print(f"✅ [CACHE] {sigla} servido desde memoria.")
        return cache[cache_key]

    # 2. Llamada Externa (Costo Crédito)
    print(f"🔄 [WEB] Descargando {sigla} desde proveedor...")
    
    params = {
        'cxml_semestre': semestre,
        'cxml_sigla': sigla,
        'cxml_nrc': '',
        'cxml_nombre': '',
        'cxml_categoria': 'TODOS',
        'cxml_area_fg': 'TODOS',
        'cxml_formato_cur': 'TODOS',
        'cxml_profesor': '',
        'cxml_campus': 'TODOS',
        'cxml_unidad_academica': 'TODOS',
        'cxml_horario_tipo_busqueda': 'si_tenga',
        'cxml_horario_tipo_busqueda_actividad': 'TODOS',
        'cxml_periodo': 'TODOS',
        'cxml_escuela': 'TODOS',
        'cxml_nivel': 'TODOS'
    }

    url_target = "https://buscacursos.uc.cl/"
    html = await get_page_content(url_target, params)
    
    # Si falla el scraping, devolvemos vacío y NO cacheamos el error
    if not html or "resultadosRow" not in html:
        return SearchResponse(semestre=semestre, cantidad=0, resultados=[])

    cursos = parse_html_to_courses(html)

    response = SearchResponse(
        semestre=semestre,
        cantidad=len(cursos),
        resultados=cursos
    )

    # Guardamos en caché
    cache[cache_key] = response
    return response


@router.get("/buscar", response_model=SearchResponse)
async def buscar_cursos(
    sigla: str = Query(..., description="Sigla del curso"),
    semestre: str = Query(..., description="Semestre")
):
    return await _buscar_curso_logic(sigla, semestre)


@router.post("/buscar-multiple", response_model=APIResponse[list[CursoPorSigla]])
async def buscar_cursos_multiple_endpoint(
    request: BusquedaMultipleRequest,
):
    """
    Search for multiple courses in parallel.
    """
    async def buscar_wrapper(sigla: str) -> CursoPorSigla:
        try:
            result = await _buscar_curso_logic(sigla, request.semestre)
            return CursoPorSigla(
                sigla=sigla,
                success=True,
                cursos=result.resultados, # Use .resultados from SearchResponse
                error=None
            )
        except Exception as e:
            return CursoPorSigla(
                sigla=sigla,
                success=False,
                cursos=[],
                error=str(e)
            )

    # Execute consistent with limit if needed, but for now gather all
    resultados = await asyncio.gather(*[buscar_wrapper(s) for s in request.siglas])
    
    exitosos = sum(1 for r in resultados if r.success)
    total_cursos = sum(len(r.cursos) for r in resultados)
    
    return APIResponse(
        success=True,
        data=list(resultados),
        message=f"Búsqueda completada: {exitosos}/{len(request.siglas)} siglas exitosas",
        meta={
            "semestre": request.semestre,
            "total_secciones": total_cursos
        }
    )


@router.get("/vacantes", response_model=list[VacanteDistribucion])
async def get_vacantes_endpoint(
    nrc: str = Query(..., description="NRC del curso"),
    semestre: str = Query(..., description="Semestre (ej: 2025-1)")
):
    """
    Get detailed vacancy distribution.
    """
    from app.services.scraper import get_vacantes_detalle
    return await get_vacantes_detalle(nrc=nrc, semestre=semestre)
