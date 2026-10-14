"""
Configuración centralizada de la aplicación.

Se usa `pydantic-settings` para cargar y VALIDAR las variables de entorno al
arranque. Si falta una variable crítica (por ejemplo `JWT_SECRET_KEY`), la app
no arranca: fallamos pronto y de forma ruidosa (fail-fast), que es la postura
segura frente a una configuración incompleta.

La función `get_settings()` está memoizada con `lru_cache`, de modo que el
objeto `Settings` se construye UNA sola vez (patrón Singleton) y se reutiliza
en toda la aplicación.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `.env` se lee desde el directorio de trabajo; `extra="ignore"` evita que
    # variables ajenas al modelo rompan el arranque.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Aplicación ---
    APP_NAME: str = "Agenda API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # --- Seguridad / JWT ---
    # Sin valor por defecto: debe definirse en el entorno. `min_length` obliga a
    # una clave de al menos 32 caracteres (HS256 necesita entropía suficiente).
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "agenda-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=1440)

    # --- Hashing de contraseñas (Argon2) ---
    # Parámetros del algoritmo Argon2id. Valores alineados con la recomendación
    # de OWASP (time_cost >= 3, memoria >= 64 MiB, paralelismo razonable).
    ARGON2_TIME_COST: int = Field(default=3, ge=1)
    ARGON2_MEMORY_COST: int = Field(default=65536, ge=8192)  # KiB (64 MiB)
    ARGON2_PARALLELISM: int = Field(default=4, ge=1)

    # --- MongoDB ---
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "agenda"

    # --- CORS ---
    # Lista blanca de orígenes permitidos. En el .env se define como JSON,
    # p. ej.: CORS_ORIGINS=["https://app.midominio.com"]
    CORS_ORIGINS: List[str] = Field(default_factory=list)

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _reject_placeholder_secret(cls, value: str) -> str:
        # Evita arrancar en producción con la clave de ejemplo de .env.example.
        if value.lower().startswith("cambiame"):
            raise ValueError(
                "JWT_SECRET_KEY no puede ser el valor de ejemplo. "
                "Genera una con: python -c \"import secrets; "
                "print(secrets.token_urlsafe(64))\""
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia única (Singleton) de `Settings`."""
    return Settings()
