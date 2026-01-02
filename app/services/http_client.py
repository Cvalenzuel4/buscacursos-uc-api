"""
HTTP client for BuscaCursos UC.

STRATEGY:
- DEVELOPMENT: Direct connection using curl_cffi (impersonating Chrome).
- PRODUCTION: Route through Cloudflare Worker to bypass IP blocking.
"""
import os
import urllib.parse
import httpx
from curl_cffi.requests import AsyncSession, Response
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("http_client")

# WORKER URL PROVIDED BY USER
WORKER_PROXY_URL = "https://proxy-uc.cristianvalmo.workers.dev/"
BUSCACURSOS_BASE = "https://buscacursos.uc.cl"

# Chrome impersonation for local dev
BROWSER_IMPERSONATE = "chrome124"


class ScrapingHTTPClient:
    """
    Hybrid HTTP Client:
    - In PRODUCTION: Uses httpx to call Cloudflare Worker.
    - In DEVELOPMENT: Uses curl_cffi for direct connection.
    """

    def __init__(self):
        self._session: AsyncSession | None = None
        self._settings = get_settings()
        self._httpx_client: httpx.AsyncClient | None = None

    async def _get_local_session(self) -> AsyncSession:
        """Get curl_cffi session for local development."""
        if self._session is None:
            self._session = AsyncSession(
                impersonate=BROWSER_IMPERSONATE,
                timeout=self._settings.http_timeout,
                verify=True,
            )
            logger.debug(f"Local Session created: {BROWSER_IMPERSONATE}")
        return self._session

    async def _get_httpx_client(self) -> httpx.AsyncClient:
        """Get httpx client for production (Worker communication)."""
        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(
                timeout=self._settings.http_timeout,
                follow_redirects=True
            )
        return self._httpx_client

    async def close(self) -> None:
        """Close all sessions."""
        if self._session:
            await self._session.close()
            self._session = None
        if self._httpx_client:
            await self._httpx_client.aclose()
            self._httpx_client = None
        logger.debug("Sessions closed")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def search_courses(
        self,
        semestre: str,
        sigla: str = "",
        nrc: str = "",
        nombre: str = "",
        profesor: str = "",
        campus: str = "",
        unidad_academica: str = "",
    ) -> Response:
        """
        Search courses using the appropriate strategy based on environment.
        """
        # Build query parameters first
        params = {
            "cxml_semestre": semestre,
            "cxml_sigla": sigla.upper() if sigla else "",
            "cxml_nrc": nrc,
            "cxml_nombre": nombre,
            "cxml_profesor": profesor,
            "cxml_campus": campus,
            "cxml_unidad_academica": unidad_academica,
            "cxml_horario_tipo_busqueda": "si_tenga",
            "cxml_horario_tipo_busqueda_actividad": "",
        }

        env = self._settings.environment.lower()
        url_base = f"{BUSCACURSOS_BASE}/"

        # --- PRODUCTION: CLOUDFLARE WORKER STRATEGY ---
        if env == "production":
            logger.info(f"🚀 Modo PROD: Routing via Cloudflare Worker -> {WORKER_PROXY_URL}")
            
            try:
                client = await self._get_httpx_client()
            except Exception as e:
                logger.error(f"❌ Error creating httpx client: {type(e).__name__}: {e}")
                raise Exception(f"Failed to create HTTP client: {e}") from e
            
            # 1. Build full target URL manually because Worker expects it in 'url' param
            query_string = urllib.parse.urlencode(params)
            target_url = f"{url_base}?{query_string}"
            
            # 2. Worker expects target URL in 'url' query param
            # httpx handles encoding of the 'url' param value itself
            proxy_params = {"url": target_url}
            
            logger.debug(f"Worker Target: {target_url}")
            logger.info(f"📡 Requesting: sigla={sigla}, semestre={semestre}")

            try:
                response = await client.get(WORKER_PROXY_URL, params=proxy_params)
            except httpx.TimeoutException as e:
                logger.error(f"❌ Timeout calling Worker: {e}")
                raise Exception(f"Worker timeout: {e}") from e
            except httpx.ConnectError as e:
                logger.error(f"❌ Connection error to Worker: {e}")
                raise Exception(f"Worker connection failed: {e}") from e
            except Exception as e:
                logger.error(f"❌ Unexpected error calling Worker: {type(e).__name__}: {e}")
                raise Exception(f"Worker request failed: {type(e).__name__}: {e}") from e

            logger.info(f"📥 Worker response: status={response.status_code}, length={len(response.text)}")

            if response.status_code != 200:
                logger.error(f"❌ Error Worker: {response.status_code}")
                # Log snippet for debugging
                logger.error(f"Worker Body Snippet: {response.text[:500]}")
                raise Exception(f"Worker failed with status {response.status_code}: {response.text[:200]}")
            
            # Verificar que la respuesta tenga contenido HTML válido
            if len(response.text) < 100:
                logger.warning(f"⚠️ Response too short ({len(response.text)} chars): {response.text}")
            
            # IMPORTANTE: Solo considerar captcha/challenge si NO hay datos de cursos
            # El HTML de BuscaCursos incluye scripts de Cloudflare que contienen "challenge"
            # pero si hay "resultadosRow" significa que los datos están presentes
            has_course_data = "resultadosRow" in response.text
            has_blocking_page = (
                ("captcha" in response.text.lower() or "cf-turnstile" in response.text.lower())
                and not has_course_data
            )
            
            if has_blocking_page:
                logger.error("❌ Captcha/Challenge page detected (no course data)")
                raise Exception("BuscaCursos returned captcha/challenge page - Worker may be blocked")
            
            if not has_course_data and len(response.text) > 1000:
                # Puede ser una página sin resultados o un error
                logger.debug(f"No resultadosRow found, checking if valid empty response...")

            # Return compatible Response object (curl_cffi style)
            # We wrap httpx response in a curl_cffi-like object or return it directly 
            # (since response.text and .status_code are compatible)
            return response

        # --- DEVELOPMENT: LOCAL CURL_CFFI STRATEGY ---
        else:
            logger.info(f"💻 Modo LOCAL: Direct connection with {BROWSER_IMPERSONATE}")
            session = await self._get_local_session()
            
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                "Referer": f"{BUSCACURSOS_BASE}/",
                "Upgrade-Insecure-Requests": "1",
            }

            # Build URL fully to be consistent with prod logic logging
            query_string = urllib.parse.urlencode(params)
            url = f"{url_base}?{query_string}"

            response = await session.get(url, headers=headers)

            if response.status_code != 200:
                logger.error(f"HTTP {response.status_code} from BuscaCursos (Local)")
                raise Exception(f"HTTP {response.status_code}: Request failed")
            
            return response

    async def fetch(self, url: str) -> Response:
        """
        Generic GET request for checks/health.
        """
        env = self._settings.environment.lower()
        
        if env == "production":
            client = await self._get_httpx_client()
            proxy_params = {"url": url}
            return await client.get(WORKER_PROXY_URL, params=proxy_params)
        else:
            session = await self._get_local_session()
            return await session.get(url)

# =============================================================================
# Global Client Instance
# =============================================================================

_http_client: ScrapingHTTPClient | None = None

def get_http_client() -> ScrapingHTTPClient:
    global _http_client
    if _http_client is None:
        _http_client = ScrapingHTTPClient()
    return _http_client

async def close_http_client() -> None:
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None
