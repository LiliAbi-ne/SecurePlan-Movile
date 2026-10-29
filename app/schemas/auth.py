"""Schemas de autenticación: credenciales de login y respuesta con el token."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Credenciales recibidas en el login (cuerpo JSON)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "S3gur4-Password!",
            }
        },
    )

    email: EmailStr = Field(..., description="Correo electrónico registrado.")
    # En login no aplicamos política de complejidad (no aporta nada y filtra
    # pistas); solo un límite amplio para acotar el tamaño de la entrada.
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Contraseña de la cuenta.",
    )


class Token(BaseModel):
    """Respuesta estándar OAuth2 con el token de acceso."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 900,
            }
        }
    )

    access_token: str = Field(..., description="JWT firmado para autenticar peticiones.")
    token_type: str = Field(default="bearer", description="Tipo de token (siempre `bearer`).")
    expires_in: int = Field(..., description="Segundos de vida del token de acceso.")
