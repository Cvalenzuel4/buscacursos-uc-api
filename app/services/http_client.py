"""
HTTP client for BuscaCursos UC.

STRATEGY (Updated 2025-01):
- Uses Cloudflare Worker as proxy for scraping.
- Worker runs from Cloudflare's edge network (residential-like IPs).
- Worker sends complete browser headers to bypass Cloudflare protection.

Worker URL: https://proxy-uc.cristianvalmo.workers.dev/

This approach is:
- 100% FREE (Cloudflare Workers free tier: 100k requests/day)
- Reliable (Cloudflare IPs are not blocked by Cloudflare)
- Fast (edge network close to users)
"""
import urllib.parse
import httpx
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("http_client")

BUSCACURSOS_BASE = "https://buscacursos.uc.cl"
WORKER_URL = "https://proxy-uc.cristianvalmo.workers.dev/"


@dataclass
class WorkerResponse:
    """Response wrapper to match previous interface."""
    status_code: int
    text: str
    
    @property
    def content(self) -> bytes:
        return self.text.encode('utf-8')


class ScrapingHTTPClient:
    """
    HTTP Client using Cloudflare Worker as proxy.
    
    Routes all requests through the Worker which:
    1. Runs from Cloudflare's edge network
    2. Sends complete browser headers (Sec-Ch-Ua, Sec-Fetch-*, etc.)
    3. Bypasses Cloudflare protection on BuscaCursos
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._settings = get_settings()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.http_timeout,
                follow_redirects=True,
            )
            logger.info("🌐 HTTP client created for Worker proxy")
        return self._client

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.debug("HTTP client closed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
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
    ) -> WorkerResponse:
        """
        Search courses via Cloudflare Worker proxy.
        
        The Worker handles all the Cloudflare bypass logic:
        - Complete Chrome headers (Sec-Ch-Ua, etc.)
        - Proper TLS negotiation
        - Edge network IPs
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

        query_string = urllib.parse.urlencode(params)
        
        # Use Worker proxy
        worker_url = f"{WORKER_URL}?{query_string}"
        
        logger.info(f"🔍 Searching via Worker: sigla={sigla}, semestre={semestre}")
        logger.debug(f"Worker URL: {worker_url}")

        try:
            client = await self._get_client()
            response = await client.get(worker_url)
            
            text = response.text
            logger.info(f"📥 Response: status={response.status_code}, length={len(text)}")

            # Check for Worker errors
            if response.status_code != 200:
                logger.error(f"❌ Worker returned HTTP {response.status_code}")
                raise Exception(f"Worker error: HTTP {response.status_code}")
            
            # Check for Cloudflare challenge in response
            if "Just a moment" in text and "Cloudflare" in text:
                logger.error("❌ Cloudflare challenge page detected (Worker blocked)")
                raise Exception("Cloudflare challenge detected. Worker may be blocked.")
            
            # Check if we got course data
            has_course_data = "resultadosRow" in text
            if has_course_data:
                logger.info(f"✅ Course data found")
            else:
                logger.debug(f"No course rows found (may be empty search)")
            
            return WorkerResponse(status_code=response.status_code, text=text)
            
        except httpx.TimeoutException as e:
            logger.error(f"❌ Worker timeout: {e}")
            raise Exception(f"Worker timeout: {e}")
        except Exception as e:
            logger.error(f"❌ Request failed: {type(e).__name__}: {e}")
            raise

    async def fetch(self, url: str) -> WorkerResponse:
        """
        Generic GET request via Worker.
        Note: This routes any URL through the Worker (for BuscaCursos paths).
        """
        client = await self._get_client()
        
        # If it's a BuscaCursos URL, route through worker
        if BUSCACURSOS_BASE in url:
            # Extract path and query from URL
            parsed = urllib.parse.urlparse(url)
            worker_url = f"{WORKER_URL}{parsed.path}"
            if parsed.query:
                worker_url += f"?{parsed.query}"
            response = await client.get(worker_url)
        else:
            response = await client.get(url)
        
        return WorkerResponse(status_code=response.status_code, text=response.text)


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