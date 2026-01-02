"""
Diagnóstico de la API BuscaCursos UC
Verifica el estado del Worker de Cloudflare y la conexión a BuscaCursos
"""
import asyncio
import httpx
import urllib.parse
from datetime import datetime

WORKER_PROXY_URL = "https://proxy-uc.cristianvalmo.workers.dev/"
BUSCACURSOS_BASE = "https://buscacursos.uc.cl"

async def main():
    print("=" * 60)
    print("DIAGNÓSTICO API BUSCACURSOS UC")
    print(f"Fecha: {datetime.now()}")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        
        # Test 1: Verificar acceso directo a BuscaCursos
        print("\n[TEST 1] Acceso directo a BuscaCursos UC...")
        try:
            direct_response = await client.get(BUSCACURSOS_BASE, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-CL,es;q=0.9",
            })
            print(f"  Status: {direct_response.status_code}")
            print(f"  Content-Type: {direct_response.headers.get('content-type', 'N/A')}")
            print(f"  Content Length: {len(direct_response.text)} chars")
            if "403" in str(direct_response.status_code) or "captcha" in direct_response.text.lower():
                print("  ⚠️ Posible bloqueo o captcha detectado")
            else:
                print("  ✅ Acceso directo OK")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test 2: Verificar Worker de Cloudflare (solo el worker)
        print("\n[TEST 2] Worker de Cloudflare (solo Worker)...")
        try:
            worker_health = await client.get(WORKER_PROXY_URL)
            print(f"  Status: {worker_health.status_code}")
            print(f"  Response: {worker_health.text[:500]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test 3: Worker + búsqueda simple
        print("\n[TEST 3] Worker + Búsqueda de MAT1610...")
        try:
            params = {
                "cxml_semestre": "2025-1",
                "cxml_sigla": "MAT1610",
                "cxml_nrc": "",
                "cxml_nombre": "",
                "cxml_profesor": "",
                "cxml_campus": "",
                "cxml_unidad_academica": "",
                "cxml_horario_tipo_busqueda": "si_tenga",
                "cxml_horario_tipo_busqueda_actividad": "",
            }
            query_string = urllib.parse.urlencode(params)
            target_url = f"{BUSCACURSOS_BASE}/?{query_string}"
            
            proxy_params = {"url": target_url}
            
            print(f"  Target URL: {target_url[:80]}...")
            
            response = await client.get(WORKER_PROXY_URL, params=proxy_params)
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"  Content Length: {len(response.text)} chars")
            
            # Analizar respuesta
            text = response.text
            if "resultadosRow" in text:
                print("  ✅ Se encontraron resultados de cursos")
            elif "captcha" in text.lower():
                print("  ⚠️ CAPTCHA detectado - Worker posiblemente bloqueado")
            elif "no se encontraron" in text.lower() or "no courses" in text.lower():
                print("  ⚠️ Sin resultados pero conexión OK")
            elif "error" in text.lower() or response.status_code >= 400:
                print("  ❌ Error en respuesta")
                print(f"  Body (primeros 500 chars): {text[:500]}")
            else:
                print(f"  ⚠️ Respuesta desconocida:")
                print(f"  Body (primeros 500 chars): {text[:500]}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test 4: Verificar headers de respuesta del Worker
        print("\n[TEST 4] Headers de respuesta del Worker...")
        try:
            target_url = f"{BUSCACURSOS_BASE}/"
            response = await client.get(WORKER_PROXY_URL, params={"url": target_url})
            print(f"  Status: {response.status_code}")
            for key, value in response.headers.items():
                if key.lower() in ['cf-ray', 'cf-cache-status', 'server', 'content-type', 'x-proxy-status']:
                    print(f"  {key}: {value}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        # Test 5: Búsqueda con semestre 2026-1 (futuro)
        print("\n[TEST 5] Búsqueda con semestre 2026-1...")
        try:
            params = {
                "cxml_semestre": "2026-1",
                "cxml_sigla": "MAT1610",
                "cxml_nrc": "",
                "cxml_nombre": "",
                "cxml_profesor": "",
                "cxml_campus": "",
                "cxml_unidad_academica": "",
                "cxml_horario_tipo_busqueda": "si_tenga",
                "cxml_horario_tipo_busqueda_actividad": "",
            }
            query_string = urllib.parse.urlencode(params)
            target_url = f"{BUSCACURSOS_BASE}/?{query_string}"
            
            response = await client.get(WORKER_PROXY_URL, params={"url": target_url})
            print(f"  Status: {response.status_code}")
            print(f"  Content Length: {len(response.text)} chars")
            if "resultadosRow" in response.text:
                print("  ✅ Se encontraron resultados")
            elif len(response.text) < 100:
                print(f"  ⚠️ Respuesta muy corta: {response.text}")
            else:
                print(f"  Body snippet: {response.text[:300]}...")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("\n" + "=" * 60)
    print("DIAGNÓSTICO COMPLETADO")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
