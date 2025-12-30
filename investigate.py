
import asyncio
import sys
import os

# Ensure app can be imported
sys.path.append(os.getcwd())

from app.services.http_client import get_http_client, close_http_client
from bs4 import BeautifulSoup

async def main():
    client = get_http_client()
    # Search for a course that likely has reserved vacancies or specific distribution
    # MAT1610 usually has many sections and reserved spots
    sigla = "MAT1610" 
    semestre = "2025-1" # Or 2026-1 as per default in code
    

    output = []
    output.append(f"Searching for {sigla} in {semestre}...")
    try:
        # First get the main page to populate session/cookies if any (important for simulated human nav)
        await client.search_courses(semestre=semestre, sigla=sigla)
        
        # Test fetching the vacancy info for one NRC from the previous output (e.g., 14778)
        nrc = "14778"
        p_semestre = "2025-1"
        
        # The URL from the onclick was ./informacionVacReserva.ajax.php...
        # So it is relative to the base URL.
        ajax_url = f"https://buscacursos.uc.cl/informacionVacReserva.ajax.php?nrc={nrc}&termcode={p_semestre}"
        
        output.append(f"Fetching vacancy details from: {ajax_url}")
        response_ajax = await client.fetch(ajax_url)
        
        output.append("Status Code: " + str(response_ajax.status_code))
        output.append("Content:")
        output.append(response_ajax.text)
        
    except Exception as e:
        output.append(f"Error: {e}")
    finally:
        with open("investigate_output.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output))
        await close_http_client()

if __name__ == "__main__":
    asyncio.run(main())
