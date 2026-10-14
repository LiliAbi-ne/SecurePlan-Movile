"""
Modelo de usuario (representación del documento en MongoDB).

Se separa deliberadamente de los *schemas* de la API:
- `UserModel` describe cómo se guarda y se lee de la base de datos.
- Los schemas (`app/schemas/*`) describen el contrato HTTP.

El `id` se mapea desde `_id` de Mongo. `PyObjectId` normaliza el `ObjectId`
de BSON a `str`, ya que JSON no sabe serializar `ObjectId`.
"""

from datetime import datetime
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, BeforeValidator

# Nombre de la colección, en un único sitio para evitar "strings mágicos".
USER_COLLECTION = "users"


def _to_object_id_str(value: object) -> str:
    """Acepta un ObjectId o un str válido y devuelve su representación en str."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str) and ObjectId.is_valid(value):
        return value
    raise ValueError("ObjectId inválido")


# Tipo reutilizable: valida/transforma cualquier entrada a un id en formato str.
PyObjectId = Annotated[str, BeforeValidator(_to_object_id_str)]


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
