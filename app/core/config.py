"""
Configuration module using Pydantic Settings for environment variable management.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # API Configuration
    app_name: str = "BuscaCursos UC API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    
    # BuscaCursos UC Configuration
    buscacursos_base_url: str = "https://buscacursos.uc.cl/"
    
    # Cache Configuration
    cache_ttl_seconds: int = 300  # 5 minutes
    cache_max_size: int = 1000   # Max number of cached responses
    
    # CORS Configuration
    allowed_origins: str = "*"
    
    # Logging
    log_level: str = "INFO"
    
    # HTTP Client Configuration
    http_timeout: float = 30.0
    http_max_retries: int = 3
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
