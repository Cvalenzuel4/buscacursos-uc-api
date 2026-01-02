import os
import urllib.parse
import httpx
from curl_cffi.requests import AsyncSession

# Global client for reusing connections if needed (optional optimization)
# For now, following the requested pattern of creating clients per request or as needed.

async def get_page_content(url_base: str, params: dict) -> str:
    env = os.getenv("ENVIRONMENT", "development")
    
    # --- PRODUCCIÓN: SCRAPINGANT ---
    if env == "production":
        api_key = os.getenv("SCRAPINGANT_API_KEY", "75a9db475ec0490d832000f28260b91f")
        if not api_key:
            print("❌ Error: Falta SCRAPINGANT_API_KEY")
            return ""

        try:
            query_string = urllib.parse.urlencode(params)
            target_url = f"{url_base}?{query_string}"
            
            # Configuración "Low Cost" con parámetros del ejemplo
            # Validado: http.client funciona donde httpx/async puede fallar en este entorno
            import http.client
            import asyncio
            
            # Construct parameters exactly as in the user example
            sa_params = {
                'url': target_url,
                'x-api-key': api_key,
                'proxy_type': 'residential',
                'browser': 'true',  # Required to avoid 423
                'return_page_source': 'true',
            }
            
            def _sync_request():
                try:
                    conn = http.client.HTTPSConnection("api.scrapingant.com", timeout=60)
                    # Helper to build query string for ScrapingAnt
                    # We need to manually encode params
                    q = urllib.parse.urlencode(sa_params)
                    path = f"/v2/general?{q}"
                    
                    conn.request("GET", path)
                    res = conn.getresponse()
                    data = res.read()
                    
                    if res.status != 200:
                        print(f"❌ ScrapingAnt Error: {res.status}")
                        return ""
                    return data.decode("utf-8")
                except Exception as e:
                    print(f"❌ ScrapingAnt Sync Error: {e}")
                    return ""

            return await asyncio.to_thread(_sync_request)

        except Exception as e:
            print(f"❌ Error Conexión Prod: {e}")
            return ""



    # --- LOCAL: CURL_CFFI ---
    else:
        print(f"💻 [LOCAL] Consultando directo...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://buscacursos.uc.cl/",
            "Upgrade-Insecure-Requests": "1"
        }
        try:
            async with AsyncSession(impersonate="chrome120") as s:
                response = await s.get(url_base, params=params, headers=headers, timeout=30)
                if response.status_code == 403: return ""
                return response.text
        except Exception as e:
            print(f"❌ Error Local: {e}")
            return ""