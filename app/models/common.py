"""
Tipos BSON reutilizables compartidos por los modelos de documentos.

`ObjectId` no es serializable a JSON, así que normalizamos cualquier id a `str`
tanto al leer de Mongo como al validar entradas de la API. Mantener este tipo en
un único módulo evita duplicar la lógica en cada modelo.
"""

from typing import Annotated

from bson import ObjectId
from pydantic import BeforeValidator


def to_object_id_str(value: object) -> str:
    """Acepta un ObjectId o un str válido y devuelve su representación en str."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str) and ObjectId.is_valid(value):
        return value
    raise ValueError("ObjectId inválido")


# Tipo reutilizable: valida/transforma cualquier entrada a un id en formato str.
PyObjectId = Annotated[str, BeforeValidator(to_object_id_str)]
