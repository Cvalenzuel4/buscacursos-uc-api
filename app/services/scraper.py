"""
BuscaCursos UC web scraper.
Extracts course data from the UC course catalog.

REAL HTML STRUCTURE (18 columns):
- 0: NRC
- 1: Sigla (with nested div/img)
- 2: Permite Retiro
- 3: ¿Se dicta en inglés?
- 4: Sección
- 5: ¿Requiere Aprob. Especial?
- 6: Área de FG
- 7: Formato Curso
- 8: Categoría
- 9: Nombre
- 10: Profesor (with link)
- 11: Campus
- 12: Créditos
- 13: Vacantes Total
- 14: Vacantes Disponibles
- 15: Vacantes Reservadas
- 16: Horario (NESTED TABLE with format: DIA:MODULOS | TIPO | SALA)
- 17: Agregar al horario

Schedule format in nested table:
  Row 1: <td>M:5</td><td>AYU</td><td>(Por Asignar)</td>
  Row 2: <td>J:5,6</td><td>CLAS</td><td>(Por Asignar)</td>
"""
import re
from typing import List

from bs4 import BeautifulSoup, Tag

from app.core.cache import cached
from app.core.logging import get_logger
from app.models.schemas import CursoSchema, HorarioSchema, VacanteDistribucion
from app.services.http_client import get_page_content

logger = get_logger("scraper")


# ============================================================================
# Day Mapping (W = Miércoles is CRITICAL)
# ============================================================================

DIAS_MAP = {
    "L": "Lunes",
    "M": "Martes",
    "W": "Miércoles",  # W = Wednesday = Miércoles
    "J": "Jueves",
    "V": "Viernes",
    "S": "Sábado",
    "D": "Domingo",
}


# ============================================================================
# Data Sanitization Helpers
# ============================================================================

def clean_int(text: str, default: int = 0) -> int:
    """
    Clean and convert string to integer.
    Handles thousands separators (dots in Spanish: 1.000).
    """
    if not text:
        return default
    try:
        cleaned = text.strip().replace(".", "").replace(",", "").replace(" ", "")
        if not cleaned:
            return default
        return int(cleaned)
    except (ValueError, AttributeError):
        return default


def extract_text(element: Tag | None) -> str:
    """Extract text from a BeautifulSoup element."""
    if element is None:
        return ""
    return element.get_text(strip=True)


# ============================================================================
# Schedule Parsing - NESTED TABLE FORMAT
# ============================================================================
#
# The schedule is in a nested <table> with rows like:
#   <tr><td>L-W:2</td><td>CLAS</td><td>(Por Asignar)</td></tr>  <-- Multi-day!
#   <tr><td>V:2</td><td>AYU</td><td>(Por Asignar)</td></tr>
#
# Formats supported (1 to 7 days):
#   - Single day: "M:5" or "J:5,6" 
#   - 2 days: "L-W:2" (Lunes AND Miércoles módulo 2)
#   - 2 days: "M-J:3" (Martes AND Jueves módulo 3)
#   - 3 days: "L-W-V:3" (Lunes, Miércoles AND Viernes módulo 3)
#   - 4+ days: "L-M-W-J:1", "L-M-W-J-V:2", "L-M-W-J-V-S:3", etc.
#
# Regex captures: DIAS:MODULOS where DIAS can have 1-7 day codes separated by hyphens
# Valid day codes: L=Lunes, M=Martes, W=Miércoles, J=Jueves, V=Viernes, S=Sábado, D=Domingo
SCHEDULE_CELL_PATTERN = re.compile(r'^([LMWJVSD](?:-[LMWJVSD])*):(.+)$', re.IGNORECASE)


def parse_schedule_table(schedule_cell: Tag) -> List[HorarioSchema]:
    """
    Parse schedule from nested table structure.
    
    Handles MULTI-DAY format like "L-W:2" or "L-W-V:3" which expands to:
      - Lunes módulo 2 (or 3)
      - Miércoles módulo 2 (or 3)
      - Viernes módulo 3 (for 3-day format)
    
    Structure:
    <td>
      <table>
        <tr>
          <td>L-W:2</td>    <!-- DIAS:MODULOS (can be multi-day) -->
          <td>CLAS</td>     <!-- TIPO -->
          <td>(sala)</td>   <!-- SALA -->
        </tr>
        ...
      </table>
    </td>
    
    Returns:
        List of HorarioSchema objects
    """
    horarios: List[HorarioSchema] = []
    
    # Find the nested table
    nested_table = schedule_cell.find("table")
    if not nested_table:
        # Fallback: try to parse as plain text
        text = schedule_cell.get_text(separator="\n", strip=True)
        if text and text not in ("-", "POR ASIGNAR", "Por Asignar"):
            logger.debug(f"No nested table, raw text: {text}")
        return horarios
    
    # Parse each row of the nested table
    rows = nested_table.find_all("tr")
    
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        
        # Cell 0: DIAS:MODULOS (e.g., "M:5", "J:5,6", "L-W:2", "M-J:3")
        dias_modulos_text = extract_text(cells[0])
        
        # Cell 1: TIPO (e.g., "AYU", "CLAS", "LAB")
        tipo = extract_text(cells[1]).upper()
        
        # Cell 2: SALA (optional)
        sala = extract_text(cells[2]) if len(cells) > 2 else None
        if sala and sala.lower() in ("por asignar", "(por asignar)", "-", ""):
            sala = None
        # Remove parentheses from sala
        if sala:
            sala = sala.strip("()")
        
        # Parse DIAS:MODULOS
        match = SCHEDULE_CELL_PATTERN.match(dias_modulos_text)
        if not match:
            logger.debug(f"Could not parse schedule cell: '{dias_modulos_text}'")
            continue
        
        dias_raw = match.group(1).upper()  # e.g., "L", "M-J", "L-W"
        modulos_raw = match.group(2)       # e.g., "2", "5,6"
        
        # Parse modules to list of integers
        modulos: List[int] = []
        for m in modulos_raw.split(","):
            m = m.strip()
            if m.isdigit():
                modulos.append(int(m))
        
        if not modulos or not tipo:
            continue
        
        # CRITICAL: Handle multi-day format (L-W, M-J, etc.)
        # Split by hyphen to get individual days
        dias_list = dias_raw.split("-")
        
        for dia_code in dias_list:
            # Map day code to full Spanish name (W = Miércoles)
            dia_nombre = DIAS_MAP.get(dia_code, dia_code)
            
            horarios.append(HorarioSchema(
                tipo=tipo,
                dia=dia_nombre,
                modulos=modulos.copy(),  # Copy to avoid shared references
                sala=sala if sala and sala.lower() != "por asignar" else None,
            ))
    
    return horarios


# ============================================================================
# HTML Table Parsing - REAL 18-COLUMN STRUCTURE
# ============================================================================

def parse_html_to_courses(html: str) -> List[CursoSchema]:
    """
    Parse BuscaCursos HTML response into CursoSchema objects.
    
    REAL Column mapping (0-indexed, 18 columns total):
    - 0: NRC
    - 1: Sigla (contains nested div with image)
    - 2: Permite Retiro
    - 3: ¿Se dicta en inglés?
    - 4: Sección
    - 5: ¿Requiere Aprob. Especial?
    - 6: Área de FG
    - 7: Formato Curso
    - 8: Categoría
    - 9: Nombre
    - 10: Profesor
    - 11: Campus
    - 12: Créditos
    - 13: Vacantes Total
    - 14: Vacantes Disponibles
    - 15: Vacantes Reservadas (lupa/link)
    - 16: Horario (NESTED TABLE)
    - 17: Agregar al horario
    
    Args:
        html: Raw HTML string from BuscaCursos
    
    Returns:
        List of CursoSchema objects
    """
    soup = BeautifulSoup(html, "lxml")
    cursos: List[CursoSchema] = []
    
    # Find all data rows with class resultadosRowPar or resultadosRowImpar
    rows = soup.find_all("tr", class_=re.compile(r"resultadosRow(Par|Impar)"))
    
    if not rows:
        logger.warning("No result rows found in HTML")
        return cursos
    
    logger.debug(f"Found {len(rows)} result rows")
    
    for row in rows:
        try:
            cols = row.find_all("td")
            
            # Need at least 17 columns
            if len(cols) < 17:
                logger.debug(f"Row has only {len(cols)} columns, skipping")
                continue
            
            # Column 0: NRC
            nrc = extract_text(cols[0])
            if not nrc or not nrc.isdigit():
                continue
            
            # Column 1: Sigla (extract text, ignoring the img tag)
            sigla_cell = cols[1]
            # Find the text after the img or in the div
            sigla = ""
            sigla_div = sigla_cell.find("div")
            if sigla_div:
                # Get all text, remove "info" icon part
                sigla = sigla_div.get_text(strip=True)
                # The sigla is the last part after any image alt text
                sigla = sigla.replace("Info", "").strip()
            else:
                sigla = extract_text(sigla_cell)
            
            if not sigla:
                continue
            
            # Column 4: Sección
            seccion = clean_int(extract_text(cols[4]), default=1)
            
            # Column 9: Nombre
            nombre = extract_text(cols[9])
            
            # Column 10: Profesor
            profesor = extract_text(cols[10])
            
            # Column 11: Campus
            campus = extract_text(cols[11])
            
            # Column 12: Créditos
            creditos = clean_int(extract_text(cols[12]))
            
            # Column 13: Vacantes Total
            vacantes_totales = clean_int(extract_text(cols[13]))
            
            # Column 14: Vacantes Disponibles
            vacantes_disponibles = clean_int(extract_text(cols[14]))
            
            # Column 16: Horario (NESTED TABLE)
            horarios = parse_schedule_table(cols[16])
            
            # Check if course has lab/taller requirement
            requiere_lab = any(h.tipo in ("LAB", "TAL") for h in horarios)
            
            cursos.append(CursoSchema(
                nrc=nrc,
                sigla=sigla,
                seccion=seccion,
                nombre=nombre,
                profesor=profesor,
                campus=campus,
                creditos=creditos,
                vacantes_totales=vacantes_totales,
                vacantes_disponibles=vacantes_disponibles,
                horarios=horarios,
                requiere_laboratorio=requiere_lab,
            ))
            
        except Exception as e:
            logger.debug(f"Error parsing course row: {e}")
            continue
    
    logger.info(f"Parsed {len(cursos)} courses from HTML")
    return cursos


# ============================================================================
# Main Scraper Functions
# ============================================================================

from app.services.http_client import get_page_content

async def get_semestres_disponibles() -> List[str]:
    """
    Get list of available semesters from BuscaCursos.
    
    Returns:
        List of semester strings (e.g., ["2026-1", "2025-2"])
    """
    from app.core.config import get_settings
    settings = get_settings()
    
    try:
        # Use simple params to get the page
        html = await get_page_content(settings.buscacursos_base_url, {})
        if not html:
            return []
            
        soup = BeautifulSoup(html, "lxml")
        
        # Find semester dropdown
        select = soup.find("select", {"name": "cxml_semestre"})
        if not select:
            return []
        
        semestres = []
        for option in select.find_all("option"):
            value = option.get("value", "")
            if re.match(r"^20\d{2}-[12S3]$", value):
                semestres.append(value)
        
        return semestres
        
    except Exception as e:
        logger.error(f"Error fetching semesters: {e}")
        return []


async def get_vacantes_detalle(nrc: str, semestre: str) -> List[VacanteDistribucion]:
    """
    Fetch detailed vacancy distribution for a specific course section (NRC).
    """
    from app.core.config import get_settings
    settings = get_settings()
    
    # URL construction
    base_url = settings.buscacursos_base_url
    url = f"{base_url}/informacionVacReserva.ajax.php"
    params = {
        'nrc': nrc,
        'termcode': semestre
    }
    
    try:
        logger.info(f"Fetching vacancies details for NRC {nrc} - {semestre}")
        html = await get_page_content(url, params)
        
        if not html:
            return []
            
        soup = BeautifulSoup(html, "lxml")
        
        # Find rows
        rows = soup.find_all("tr", class_=re.compile(r"resultadosRow(Par|Impar)"))
        
        results: List[VacanteDistribucion] = []
        
        for row in rows:
            cols = row.find_all("td")
            # Need at least 9 cols
            if len(cols) < 9:
                continue
            
            # Extract data
            escuela = extract_text(cols[1])
            programa = extract_text(cols[2])
            concentracion = extract_text(cols[3])
            cohorte = extract_text(cols[4])
            periodo_admision = extract_text(cols[5])
            ofrecidas = clean_int(extract_text(cols[6]))
            ocupadas = clean_int(extract_text(cols[7]))
            disponibles = clean_int(extract_text(cols[8]))
            
            results.append(VacanteDistribucion(
                escuela=escuela,
                programa=programa,
                concentracion=concentracion,
                cohorte=cohorte,
                periodo_admision=periodo_admision,
                ofrecidas=ofrecidas,
                ocupadas=ocupadas,
                disponibles=disponibles
            ))
            
        logger.info(f"Found {len(results)} vacancy types for NRC {nrc}")
        return results
        
    except Exception as e:
        logger.error(f"Error fetching vacancy details for {nrc}: {e}")
        return []
