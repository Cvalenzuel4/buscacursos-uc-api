"""
Debug: verificar qué hay en la respuesta del Worker
"""
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://proxy-uc.cristianvalmo.workers.dev/",
            params={"url": "https://buscacursos.uc.cl/?cxml_semestre=2025-1&cxml_sigla=MAT1610"}
        )
        
        text = response.text
        print(f"Status: {response.status_code}")
        print(f"Length: {len(text)} chars")
        print(f"\n--- Buscando palabras clave ---")
        print(f"'resultadosRow' found: {'resultadosRow' in text}")
        print(f"'captcha' found: {'captcha' in text.lower()}")
        print(f"'challenge' found: {'challenge' in text.lower()}")
        
        # Buscar contexto de 'challenge'
        if 'challenge' in text.lower():
            idx = text.lower().find('challenge')
            print(f"\nContexto de 'challenge': ...{text[max(0,idx-100):idx+100]}...")
        
        # Verificar si hay cursos
        print(f"\n'Cálculo' found: {'Cálculo' in text or 'Calculo' in text}")
        print(f"'MAT1610' found: {'MAT1610' in text}")

if __name__ == "__main__":
    asyncio.run(main())
