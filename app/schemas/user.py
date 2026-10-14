"""
Schemas de usuario: validación estricta de entrada y respuesta segura.

Regla de oro (OWASP API3 - Excessive Data Exposure): el `password_hash` jamás
sale en una respuesta. El schema `UserPublic` define exactamente qué campos se
exponen, y FastAPI filtra cualquier campo extra del modelo interno.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_PASSWORD_MIN_LENGTH = 12
_PASSWORD_MAX_LENGTH = 128


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    """Payload del registro. `extra="forbid"` rechaza campos desconocidos."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(..., min_length=_PASSWORD_MIN_LENGTH, max_length=_PASSWORD_MAX_LENGTH)

    @field_validator("password")
    @classmethod
    def _enforce_password_policy(cls, value: str) -> str:
        """Política mínima: mayúscula, minúscula, dígito y carácter especial."""
        if not any(c.isupper() for c in value):
            raise ValueError("La contraseña debe incluir al menos una mayúscula")
        if not any(c.islower() for c in value):
            raise ValueError("La contraseña debe incluir al menos una minúscula")
        if not any(c.isdigit() for c in value):
            raise ValueError("La contraseña debe incluir al menos un dígito")
        if not any(not c.isalnum() for c in value):
            raise ValueError("La contraseña debe incluir al menos un carácter especial")
        return value


class UserPublic(UserBase):
    """Representación pública del usuario que se devuelve por la API."""

    # Permite construir el schema a partir del `UserModel` (que tiene `id`).
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
