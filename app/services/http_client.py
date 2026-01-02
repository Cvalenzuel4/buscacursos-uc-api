"""
HTTP client for BuscaCursos UC.

STRATEGY (Updated 2026-01):
- Uses curl_cffi with Chrome impersonation in ALL environments.
- curl_cffi can bypass Cloudflare protection by mimicking real browsers.
- No external proxy/worker needed - direct connection with TLS fingerprint spoofing.

This approach is:
- 100% FREE (no external services)
- More reliable than Workers (which can get blocked)
- Works in both development and production
"""
import random
import urllib.parse
from curl_cffi.requests import AsyncSession, Response
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("http_client")

BUSCACURSOS_BASE = "https://buscacursos.uc.cl"

# Chrome versions to rotate (all supported by curl_cffi)
BROWSER_VERSIONS = [
    "chrome120",
    "chrome119", 
    "chrome116",
    "chrome110",
    "chrome107",
    "chrome104",
    "chrome101",
    "chrome100",
    "chrome99",
]


class ScrapingHTTPClient:
    """
    HTTP Client using curl_cffi for Cloudflare bypass.
    
    Uses TLS fingerprint impersonation to appear as a real browser.
    This works because curl_cffi implements the same TLS handshake as Chrome.
    """

    def __init__(self):
        self._session: AsyncSession | None = None
        self._settings = get_settings()
        self._current_browser = random.choice(BROWSER_VERSIONS)
        self._request_count = 0

    async def _get_session(self) -> AsyncSession:
        """Get or create curl_cffi session with browser impersonation."""
        # Rotate browser every 10 requests to avoid fingerprinting
        if self._request_count > 0 and self._request_count % 10 == 0:
            if self._session:
                await self._session.close()
                self._session = None
            self._current_browser = random.choice(BROWSER_VERSIONS)
            logger.debug(f"Rotated browser to: {self._current_browser}")
        
        if self._session is None:
            self._session = AsyncSession(
                impersonate=self._current_browser,
                timeout=self._settings.http_timeout,
                verify=True,
            )
            logger.info(f"🌐 Session created with browser: {self._current_browser}")
        
        return self._session

    def _get_headers(self) -> dict:
        """Get realistic browser headers."""
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Referer": f"{BUSCACURSOS_BASE}/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.debug("Session closed")

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
        Search courses using curl_cffi with browser impersonation.
        
        This bypasses Cloudflare by:
        1. Using the same TLS fingerprint as Chrome
        2. Sending realistic browser headers
        3. Rotating browser versions periodically
        """
        self._request_count += 1
        
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

        query_string = urllib.parse.urlencode(params)
        url = f"{BUSCACURSOS_BASE}/?{query_string}"

        logger.info(f"🔍 Searching: sigla={sigla}, semestre={semestre}")
        logger.debug(f"URL: {url}")

        try:
            session = await self._get_session()
            headers = self._get_headers()
            
            response = await session.get(url, headers=headers)
            
            logger.info(f"📥 Response: status={response.status_code}, length={len(response.text)}")

            # Check for blocking
            if response.status_code == 403:
                logger.error(f"❌ 403 Forbidden - Cloudflare block detected")
                # Close session to force new one with different browser
                await self.close()
                raise Exception(f"Cloudflare blocked request (403). Will retry with different browser.")
            
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}")
                raise Exception(f"HTTP {response.status_code}: Request failed")
            
            # Check for Cloudflare challenge page
            text = response.text
            if "Just a moment" in text and "Cloudflare" in text:
                logger.error("❌ Cloudflare challenge page detected")
                await self.close()
                raise Exception("Cloudflare challenge detected. Will retry with different browser.")
            
            # Check if we got course data
            has_course_data = "resultadosRow" in text
            if has_course_data:
                logger.info(f"✅ Course data found")
            else:
                logger.debug(f"No course rows found (may be empty search)")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Request failed: {type(e).__name__}: {e}")
            raise

    async def fetch(self, url: str) -> Response:
        """
        Generic GET request.
        """
        self._request_count += 1
        session = await self._get_session()
        headers = self._get_headers()
        return await session.get(url, headers=headers)


# =============================================================================
# =============================================================================
# Global Client Instance
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