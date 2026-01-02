"""
Test que simula exactamente el flujo de la API en producción
"""
import asyncio
import os
import sys

# Simular entorno de producción
os.environ["ENVIRONMENT"] = "production"

# Agregar el directorio al path
sys.path.insert(0, ".")

async def main():
    print("=" * 60)
    print("TEST DE FLUJO COMPLETO DE LA API (MODO PRODUCCIÓN)")
    print("=" * 60)
    
    try:
        from app.core.config import get_settings
        from app.services.http_client import get_http_client, ScrapingHTTPClient
        from app.services.scraper import parse_html_to_courses
        
        settings = get_settings()
        print(f"\nEntorno configurado: {settings.environment}")
        print(f"Timeout HTTP: {settings.http_timeout}s")
        
        client = get_http_client()
        
        print("\n[TEST 1] Búsqueda de MAT1610 en 2025-1...")
        try:
            response = await client.search_courses(
                semestre="2025-1",
                sigla="MAT1610"
            )
            print(f"  Status: {response.status_code}")
            print(f"  Content Length: {len(response.text)} chars")
            
            # Parsear HTML
            cursos = parse_html_to_courses(response.text)
            print(f"  Cursos encontrados: {len(cursos)}")
            
            if cursos:
                print(f"  ✅ Primer curso: {cursos[0].nombre} - Sección {cursos[0].seccion}")
            else:
                print(f"  ⚠️ No se parsearon cursos")
                # Mostrar snippet del HTML para debug
                print(f"  HTML snippet: {response.text[:500]}")
                
        except Exception as e:
            print(f"  ❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n[TEST 2] Búsqueda de ICS2123 en 2026-1...")
        try:
            response = await client.search_courses(
                semestre="2026-1",
                sigla="ICS2123"
            )
            print(f"  Status: {response.status_code}")
            print(f"  Content Length: {len(response.text)} chars")
            
            cursos = parse_html_to_courses(response.text)
            print(f"  Cursos encontrados: {len(cursos)}")
            
            if cursos:
                for curso in cursos[:3]:
                    print(f"    - {curso.sigla} Sec {curso.seccion}: {curso.nombre} ({curso.profesor})")
            
        except Exception as e:
            print(f"  ❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Cerrar cliente
        await client.close()
        
        print("\n" + "=" * 60)
        print("TEST COMPLETADO")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error fatal: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
