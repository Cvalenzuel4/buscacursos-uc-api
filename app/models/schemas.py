"""
Pydantic schemas for API request/response validation.
"""
import re
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Schedule/Horario Schemas
# ============================================================================

class HorarioSchema(BaseModel):
    """Schema for a single schedule block."""
    
    tipo: str = Field(
        ...,
        description="Tipo de actividad: CLAS, AYU, LAB, TAL, TER, PRA, etc.",
        examples=["CLAS", "AYU", "LAB"]
    )
    dia: str = Field(
        ...,
        description="Día de la semana en español",
        examples=["Lunes", "Martes", "Miércoles"]
    )
    modulos: list[int] = Field(
        default_factory=list,
        description="Lista de módulos (1-8)",
        examples=[[1, 2], [3, 4, 5]]
    )
    sala: str | None = Field(
        default=None,
        description="Sala asignada",
        examples=["A-101", "B-302"]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tipo": "CLAS",
                "dia": "Lunes",
                "modulos": [1, 2],
                "sala": "A-101"
            }
        }


# ============================================================================
# Course/Curso Schemas
# ============================================================================

class CursoSchema(BaseModel):
    """Schema for a course section."""
    
    nrc: str = Field(
        ...,
        description="Número de Referencia del Curso (NRC)",
        examples=["12345"]
    )
    sigla: str = Field(
        ...,
        description="Sigla del curso",
        examples=["ICS2123"]
    )
    seccion: int = Field(
        ...,
        description="Número de sección",
        ge=1,
        examples=[1, 2]
    )
    nombre: str = Field(
        ...,
        description="Nombre del curso",
        examples=["Estructuras de Datos"]
    )
    profesor: str = Field(
        ...,
        description="Nombre del profesor",
        examples=["Juan Pérez"]
    )
    campus: str = Field(
        default="",
        description="Campus donde se imparte",
        examples=["San Joaquín", "Casa Central"]
    )
    creditos: int = Field(
        default=0,
        description="Créditos del curso",
        ge=0,
        examples=[10, 15]
    )
    vacantes_totales: int = Field(
        default=0,
        description="Número total de vacantes",
        ge=0
    )
    vacantes_disponibles: int = Field(
        default=0,
        description="Número de vacantes disponibles",
        ge=0
    )
    horarios: list[HorarioSchema] = Field(
        default_factory=list,
        description="Lista de horarios del curso"
    )
    requiere_laboratorio: bool = Field(
        default=False,
        description="Indica si el curso tiene laboratorio asociado"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "nrc": "12345",
                "sigla": "ICS2123",
                "seccion": 1,
                "nombre": "Estructuras de Datos",
                "profesor": "Juan Pérez",
                "campus": "San Joaquín",
                "creditos": 10,
                "vacantes_totales": 80,
                "vacantes_disponibles": 15,
                "horarios": [
                    {"tipo": "CLAS", "dia": "Lunes", "modulos": [1, 2], "sala": "A-101"},
                    {"tipo": "AYU", "dia": "Miércoles", "modulos": [5], "sala": "B-201"}
                ],
                "requiere_laboratorio": False
            }
        }


# ============================================================================
# Request Validation Schemas
# ============================================================================

class BusquedaParams(BaseModel):
    """Validated parameters for course search."""
    
    sigla: str = Field(
        ...,
        description="Sigla del curso (ej: ICS2123, MAT1610)",
        min_length=3,
        max_length=10
    )
    semestre: str = Field(
        ...,
        description="Semestre en formato YYYY-S donde S es 1, 2 o S",
        examples=["2025-1", "2025-2", "2025-S"]
    )
    profesor: str | None = Field(
        default=None,
        description="Filtrar por nombre del profesor (búsqueda parcial)",
        min_length=2
    )
    campus: str | None = Field(
        default=None,
        description="Filtrar por campus"
    )
    
    @field_validator("sigla")
    @classmethod
    def validate_sigla(cls, v: str) -> str:
        """Validate and normalize course code format."""
        v = v.strip().upper()
        # Pattern: 3 letters, 3-4 digits, optional letter
        if not re.match(r"^[A-Z]{3}\d{3,4}[A-Z]?$", v):
            raise ValueError(
                f"Formato de sigla inválido: '{v}'. "
                "Debe ser 3 letras + 3-4 dígitos + letra opcional (ej: ICS2123, MAT1610)"
            )
        return v
    
    @field_validator("semestre")
    @classmethod
    def validate_semestre(cls, v: str) -> str:
        """Validate semester format."""
        v = v.strip()
        if not re.match(r"^20\d{2}-[12S]$", v):
            raise ValueError(
                f"Formato de semestre inválido: '{v}'. "
                "Debe ser YYYY-S donde S es 1, 2 o S (ej: 2025-1, 2025-S)"
            )
        return v


# ============================================================================
# API Response Wrappers
# ============================================================================

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API success response wrapper."""
    
    success: bool = True
    data: T
    message: str | None = None
    meta: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard API error response."""
    
    success: bool = False
    error: str
    detail: str | None = None
    code: str | None = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "VALIDATION_ERROR",
                "detail": "Formato de sigla inválido",
                "code": "INVALID_SIGLA"
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = "healthy"
    version: str
    cache_stats: dict[str, Any] | None = None
