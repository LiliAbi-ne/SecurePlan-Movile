"""
Modelo de usuario (representación del documento en MongoDB).

Se separa deliberadamente de los *schemas* de la API:
- `UserModel` describe cómo se guarda y se lee de la base de datos.
- Los schemas (`app/schemas/*`) describen el contrato HTTP.

El `id` se mapea desde `_id` de Mongo. `PyObjectId` (definido en
`app.models.common`) normaliza el `ObjectId` de BSON a `str`, ya que JSON no sabe
serializar `ObjectId`.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.common import PyObjectId

# Nombre de la colección, en un único sitio para evitar "strings mágicos".
USER_COLLECTION = "users"


class UserModel(BaseModel):
    """Documento de usuario tal como vive en MongoDB."""

    # `populate_by_name` permite construir el modelo usando el alias `_id`.
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    email: EmailStr
    # NUNCA se expone en respuestas: ver `UserPublic`.
    password_hash: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
