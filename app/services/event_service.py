"""
Servicio de eventos: encapsula el acceso a la colección `events`.

Punto CRÍTICO de seguridad (anti-IDOR / OWASP API1 BOLA): TODAS las operaciones
reciben el `user_id` del usuario autenticado y lo incluyen SIEMPRE en el filtro
de MongoDB. No existe ningún método que resuelva un evento por su `_id` sin
acotar por dueño, de modo que es estructuralmente imposible leer, modificar o
borrar el evento de otro usuario.

El `user_id` se toma del token (ver `get_current_user`), nunca del payload.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.database import get_database
from app.models.event import EVENT_COLLECTION, EventModel, Priority
from app.schemas.event import EventCreate, EventUpdate, normalize_category_filter


class EventService:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[EVENT_COLLECTION]

    async def create(self, user_id: str, data: EventCreate) -> EventModel:
        """Crea un evento cuyo dueño es SIEMPRE el usuario autenticado."""
        now = datetime.now(timezone.utc)
        document = {
            # El dueño lo impone el servidor; jamás se lee de `data`.
            "user_id": ObjectId(user_id),
            "title": data.title,
            "description": data.description,
            "date": data.date,
            "time": data.time,
            "category": data.category,
            "priority": data.priority.value,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return EventModel.model_validate(document)

    async def list_for_user(
        self,
        user_id: str,
        category: Optional[str] = None,
        priority: Optional[Priority] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[EventModel]:
        """Lista los eventos del usuario, con filtros y paginación."""
        # El filtro por dueño es la base innegociable del aislamiento.
        query: dict = {"user_id": ObjectId(user_id)}

        if category:
            query["category"] = normalize_category_filter(category)
        if priority is not None:
            query["priority"] = priority.value

        date_range: dict = {}
        if date_from:
            date_range["$gte"] = date_from
        if date_to:
            date_range["$lte"] = date_to
        if date_range:
            query["date"] = date_range

        cursor = (
            self._collection.find(query)
            .sort([("date", 1), ("time", 1)])
            .skip(offset)
            .limit(limit)
        )
        return [EventModel.model_validate(document) async for document in cursor]

    async def get_for_user(self, event_id: str, user_id: str) -> Optional[EventModel]:
        """Devuelve el evento si existe Y pertenece al usuario; si no, None."""
        if not ObjectId.is_valid(event_id):
            return None
        document = await self._collection.find_one(
            {"_id": ObjectId(event_id), "user_id": ObjectId(user_id)}
        )
        return EventModel.model_validate(document) if document else None

    async def update_for_user(
        self, event_id: str, user_id: str, data: EventUpdate
    ) -> Optional[EventModel]:
        """Actualiza (parcial) un evento propio. Devuelve None si no es suyo."""
        if not ObjectId.is_valid(event_id):
            return None

        # Solo los campos enviados (`exclude_unset`); `description=None` limpia.
        updates = data.model_dump(exclude_unset=True)
        if updates.get("priority") is not None:
            updates["priority"] = Priority(updates["priority"]).value
        updates["updated_at"] = datetime.now(timezone.utc)

        document = await self._collection.find_one_and_update(
            {"_id": ObjectId(event_id), "user_id": ObjectId(user_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return EventModel.model_validate(document) if document else None

    async def delete_for_user(self, event_id: str, user_id: str) -> bool:
        """Elimina un evento propio. Devuelve True solo si borró algo."""
        if not ObjectId.is_valid(event_id):
            return False
        result = await self._collection.delete_one(
            {"_id": ObjectId(event_id), "user_id": ObjectId(user_id)}
        )
        return result.deleted_count == 1


def get_event_service(
    database: AsyncIOMotorDatabase = Depends(get_database),
) -> EventService:
    """Dependencia de FastAPI que construye el servicio con la BD activa."""
    return EventService(database)
