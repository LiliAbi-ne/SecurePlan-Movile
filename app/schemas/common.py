"""
Schemas transversales a toda la API.

`ErrorResponse` documenta la forma estándar de error que produce FastAPI al
lanzar una `HTTPException`: `{"detail": "..."}`. Se referencia desde el parámetro
`responses` de los endpoints para que la documentación OpenAPI muestre el cuerpo
real de los errores (401/403/404/409/422), en lugar de un esquema vacío.
"""

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Cuerpo estándar de un error de la API."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"detail": "Evento no encontrado"}}
    )

    detail: str = Field(..., description="Descripción del error en lenguaje natural")
