
import asyncio
import sys
import os

sys.path.append(os.getcwd())

from app.services.scraper import get_vacantes_detalle

async def main():
    nrc = "14778" # From previous investigation (Calculo I)
    semestre = "2025-1"
    
    output = []
    output.append(f"Fetching vacancies for NRC {nrc}...")
    try:
        results = await get_vacantes_detalle(nrc, semestre)
        
        output.append(f"Got {len(results)} rows.")
        for res in results:
            output.append(f"{res.escuela}: {res.disponibles} disponibles (de {res.ofrecidas})")
    except Exception as e:
        output.append(f"Error: {e}")
        
    with open("verify_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    asyncio.run(main())
