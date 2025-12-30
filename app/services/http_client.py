"""
HTTP client using Hybrid Strategy:
- Local (Development): curl_cffi direct connection (Anti-Fingerprint)
- Production (Render): httpx via Google Apps Script Proxy (Anti-IP Block)
"""
import os
from urllib.parse import urlencode

import httpx
from curl_cffi.requests import AsyncSession, Response
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("http_client")

# =============================================================================
# Constants
# =============================================================================

BUSCACURSOS_BASE = "https://buscacursos.uc.cl"
GAS_PROXY_URL = "https://script.google.com/macros/s/AKfycbyn9R4plCwGpy0dYvSnvVlgTT53XWPgy01aovlidHAFfCupgUrT_FBE8BLk0HX2-yP1/exec"

# Local chrome impersonation
BROWSER_IMPERSONATE = "chrome120"


# =============================================================================
# Headers - Minimal & Clean (For Local)
# =============================================================================

def get_browser_headers() -> dict[str, str]:
    """Headers for local curl_cffi requests."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": f"{BUSCACURSOS_BASE}/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Connection": "keep-alive"
    }


# =============================================================================
# Main HTTP Client Class - Hybrid
# =============================================================================

class ScrapingHTTPClient:
    """
    Hybrid HTTP Client.
    Adapts strategy based on ENVIRONMENT variable.
    """
    
    def __init__(self):
        self._session: AsyncSession | None = None
        self._settings = get_settings()
        self._env = os.getenv("ENVIRONMENT", "development")
    
    async def _get_local_session(self) -> AsyncSession:
        """Get or create the async session for Local/Dev."""
        if self._session is None:
            self._session = AsyncSession(
                impersonate=BROWSER_IMPERSONATE,
                timeout=self._settings.http_timeout,
                verify=True,
                # proxy=self._settings.proxy_url # Legacy proxy support if needed
            )
            logger.debug(f"Local Session created with {BROWSER_IMPERSONATE}")
        return self._session
    
    async def close(self) -> None:
        """Close the session (only relevant for local)."""
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
    ) -> Response | httpx.Response:
        """
        Search courses using Hybrid Strategy.
        """
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
        
        # Build Target URL
        query_string = urlencode(params)
        target_url = f"{BUSCACURSOS_BASE}/?{query_string}"
        
        logger.info(f"[{self._env.upper()}] Fetching: {target_url}")

        if self._env == "production":
            return await self._fetch_production(target_url)
        else:
            return await self._fetch_local(target_url)

    async def fetch(self, url: str) -> Response | httpx.Response:
        """Generic GET request using Hybrid Strategy."""
        logger.info(f"[{self._env.upper()}] Generic Fetch: {url}")
        
        if self._env == "production":
            return await self._fetch_production(url)
        else:
            return await self._fetch_local(url)

    # --- STRATEGIES ---

    async def _fetch_production(self, target_url: str) -> httpx.Response:
        """
        [PRODUCTION] Use httpx + Google Apps Script Proxy.
        """
        proxy_params = {"url": target_url}
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(GAS_PROXY_URL, params=proxy_params)
                
                if response.status_code != 200:
                    logger.error(f"❌ Google Proxy Error: {response.status_code}")
                    # Return mock response to avoid crash, or raise? 
                    # Raising allows generic handler to catch it.
                    response.raise_for_status()
                
                logger.info("✅ Proxy request successful")
                return response
                
        except Exception as e:
            logger.error(f"❌ Production Connection Error: {e}")
            raise

    async def _fetch_local(self, target_url: str) -> Response:
        """
        [LOCAL] Use curl_cffi directly.
        """
        session = await self._get_local_session()
        headers = get_browser_headers()
        
        # Retry logic for local flakes
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        async def _make_request():
            return await session.get(target_url, headers=headers)

        try:
            response = await _make_request()
            
            if response.status_code == 403:
                logger.error("❌ LOCAL BLOCK (403): Cloudflare/WAF detected script.")
            elif response.status_code != 200:
                logger.error(f"HTTP {response.status_code} from BuscaCursos (Local)")
                raise Exception(f"HTTP {response.status_code}")
                
            return response
        except Exception as e:
            logger.error(f"❌ Local Connection Error: {e}")
            raise

    # Legacy compatibility
    async def get_session(self) -> AsyncSession:
        return await self._get_local_session()
    
    async def ensure_session(self) -> None:
        await self._get_local_session()


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
