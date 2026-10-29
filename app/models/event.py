"""
Modelo de evento/actividad (representación del documento en MongoDB).

Igual que `UserModel`, se separa de los schemas de la API:
- `EventModel` describe cómo se guarda y se lee de la base de datos.
- Los schemas (`app/schemas/event.py`) describen el contrato HTTP.

Dos decisiones importantes:

1. `user_id` es el DUEÑO del evento y el ancla de la protección anti-IDOR. Se
   guarda como `ObjectId` y toda consulta filtra por él, de modo que un usuario
   no puede alcanzar los eventos de otro ni manipulando el `_id`.

2. `date` y `time` se guardan como STRING (`"YYYY-MM-DD"` y `"HH:MM"`), no como
   tipos `date`/`time`. Motivo: PyMongo no puede codificar `datetime.time`; y en
   formato ISO el orden y los rangos (`$gte`/`$lte`) funcionan lexicográficamente
   sin conversiones.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import PyObjectId

# Nombre de la colección, en un único sitio para evitar "strings mágicos".
EVENT_COLLECTION = "events"

# Categorías sugeridas. NO es una lista cerrada: el usuario puede crear las suyas
# (el schema solo exige que el valor esté bien formado).
DEFAULT_CATEGORIES = ("personal", "trabajo", "estudio", "salud", "ocio", "otro")


class Priority(str, Enum):
    """Prioridad del evento. Enum cerrado: cualquier otro valor se rechaza."""

    baja = "baja"
    media = "media"
    alta = "alta"


class EventModel(BaseModel):
    """Documento de evento tal como vive en MongoDB."""

    # `populate_by_name` permite construir el modelo usando el alias `_id`.
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    # Dueño del evento. Se copia del usuario autenticado, NUNCA del payload.
    user_id: PyObjectId
    title: str
    description: Optional[str] = None
    date: str  # "YYYY-MM-DD"
    time: str  # "HH:MM"
    category: str
    priority: Priority
    created_at: datetime
    updated_at: datetime
