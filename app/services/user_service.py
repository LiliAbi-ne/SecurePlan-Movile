"""
Servicio de usuarios: encapsula el acceso a la colección `users`.

Mantener la lógica de datos aquí (y no en el router) permite testear el acceso
a MongoDB de forma aislada y mantener los endpoints finos, dedicados solo al
protocolo HTTP.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.security import hash_password
from app.models.user import USER_COLLECTION, UserModel
from app.schemas.user import UserCreate


def _normalize_email(email: str) -> str:
    # Normalizamos para que el índice único y las búsquedas sean consistentes.
    return email.strip().lower()


class UserService:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database[USER_COLLECTION]

    async def get_by_email(self, email: str) -> Optional[UserModel]:
        document = await self._collection.find_one({"email": _normalize_email(email)})
        return UserModel.model_validate(document) if document else None

    async def get_by_id(self, user_id: str) -> Optional[UserModel]:
        # Validar el id evita lanzar una excepción por un ObjectId mal formado.
        if not ObjectId.is_valid(user_id):
            return None
        document = await self._collection.find_one({"_id": ObjectId(user_id)})
        return UserModel.model_validate(document) if document else None

    async def create(self, data: UserCreate) -> UserModel:
        now = datetime.now(timezone.utc)
        document = {
            "email": _normalize_email(data.email),
            "password_hash": await hash_password(data.password),
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return UserModel.model_validate(document)


def get_user_service(
    database: AsyncIOMotorDatabase = Depends(get_database),
) -> UserService:
    """Dependencia de FastAPI que construye el servicio con la BD activa."""
    return UserService(database)
