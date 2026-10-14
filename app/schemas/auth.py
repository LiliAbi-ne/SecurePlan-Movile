"""Schemas de autenticación: credenciales de login y respuesta con el token."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Credenciales recibidas en el login (cuerpo JSON)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    # En login no aplicamos política de complejidad (no aporta nada y filtra
    # pistas); solo un límite amplio para acotar el tamaño de la entrada.
    password: str = Field(..., min_length=1, max_length=128)


class Token(BaseModel):
    """Respuesta estándar OAuth2 con el token de acceso."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos de vida del token
