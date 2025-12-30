"""
HTTP client using curl_cffi for Cloudflare bypass.

Strategy: KISS - Single GET request to the main page with query parameters.
No retries, no session recreation, no complex handshakes.
Simplicity is the best anti-bot strategy.
"""
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession, Response

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("http_client")


# =============================================================================
# Constants
# =============================================================================

BUSCACURSOS_BASE = "https://buscacursos.uc.cl"

# Chrome 120 impersonation for TLS fingerprint bypass
BROWSER_IMPERSONATE = "chrome120"


# =============================================================================
# Headers - Minimal & Clean
# =============================================================================

def get_browser_headers() -> dict[str, str]:
    """
    Minimal headers that mimic a real Chrome browser.
    Less is more - excessive headers trigger WAF.
    """
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": f"{BUSCACURSOS_BASE}/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
    }


# =============================================================================
# Main HTTP Client Class - Ultra Simple
# =============================================================================

class ScrapingHTTPClient:
    """
    Simplified HTTP client - single request, no retries, no tricks.
    
    If it fails, it fails. Simplicity avoids bot detection.
    The curl_cffi impersonation handles TLS fingerprint.
    """
    
    def __init__(self):
        self._session: AsyncSession | None = None
        self._settings = get_settings()
    
    async def _get_session(self) -> AsyncSession:
        """Get or create the async session."""
        if self._session is None:
            self._session = AsyncSession(
                impersonate=BROWSER_IMPERSONATE,
                timeout=self._settings.http_timeout,
                verify=True,
            )
            logger.debug(f"Session created with {BROWSER_IMPERSONATE} impersonation")
        return self._session
    
    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("Session closed")
    
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
        Search courses with a single GET request.
        
        NO RETRIES. NO SESSION RECREATION. KISS PRINCIPLE.
        
        Args:
            semestre: Semester (e.g., "2025-1")
            sigla: Course code (e.g., "ICS2123")
            nrc: NRC code
            nombre: Course name
            profesor: Professor name
            campus: Campus filter
            unidad_academica: Academic unit
        
        Returns:
            Response object with HTML content
        
        Raises:
            Exception: On any HTTP error (including 403)
        """
        session = await self._get_session()
        headers = get_browser_headers()
        
        # Build query parameters
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
        
        # Build URL with query string
        query_string = urlencode(params)
        url = f"{BUSCACURSOS_BASE}/?{query_string}"
        
        logger.info(f"Fetching: {BUSCACURSOS_BASE}/ | sigla={sigla}, semestre={semestre}")
        
        # Single request - no retries
        response = await session.get(url, headers=headers)
        
        logger.debug(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"HTTP {response.status_code} from BuscaCursos")
            raise Exception(f"HTTP {response.status_code}: Request failed")
        
        logger.info("Successfully retrieved search results")
        return response
    
    async def fetch(self, url: str) -> Response:
        """Generic GET request for other pages."""
        session = await self._get_session()
        headers = get_browser_headers()
        
        response = await session.get(url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: Failed to fetch {url}")
        
        return response
    
    # Legacy compatibility
    async def get_session(self) -> AsyncSession:
        """Legacy alias for _get_session."""
        return await self._get_session()
    
    async def ensure_session(self) -> None:
        """Legacy - kept for compatibility."""
        await self._get_session()


# =============================================================================
# Global Client Instance (Singleton)
# =============================================================================

_http_client: ScrapingHTTPClient | None = None


def get_http_client() -> ScrapingHTTPClient:
    """Get the global HTTP client instance."""
    global _http_client
    if _http_client is None:
        _http_client = ScrapingHTTPClient()
    return _http_client


async def close_http_client() -> None:
    """Close the global HTTP client."""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None
