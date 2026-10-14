"""
Conexión a MongoDB con patrón SINGLETON.

Por qué: crear un `AsyncIOMotorClient` nuevo por petición agotaría el pool de
conexiones y dispararía la latencia. Motor ya gestiona un pool interno, así que
lo correcto es mantener UNA única instancia del cliente durante todo el ciclo de
vida del proceso.

`MongoConnection` implementa explícitamente el patrón Singleton (instancia única
por proceso) y se engancha al ciclo de vida `lifespan` de FastAPI: se abre al
arrancar y se cierra al apagar, liberando el pool de forma limpia.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings
from app.models.user import USER_COLLECTION

logger = logging.getLogger(__name__)


class MongoConnection:
    """Envoltura Singleton sobre el cliente asíncrono de MongoDB."""

    _instance: "MongoConnection | None" = None
    _client: AsyncIOMotorClient | None = None
    _database: AsyncIOMotorDatabase | None = None

    def __new__(cls) -> "MongoConnection":
        # Punto clave del patrón: garantizamos una sola instancia en el proceso.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Abre la conexión (idempotente). Se llama una vez en el `lifespan`."""
        if self._client is not None:
            return

        settings = get_settings()
        self._client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            # `uuidRepresentation` evita la deprecación de PyMongo y fija un
            # comportamiento consistente para tipos BSON.
            uuidRepresentation="standard",
            # Corta operaciones colgadas en lugar de esperar de forma indefinida.
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
        )
        self._database = self._client[settings.MONGODB_DB_NAME]

        # "Ping" de verificación: falla temprano si la URL o el servidor no son
        # alcanzables, en vez de descubrirlo en la primera petición del cliente.
        await self._client.admin.command("ping")
        logger.info("Conexión a MongoDB establecida (db=%s)", settings.MONGODB_DB_NAME)

        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        """Crea los índices necesarios para integridad y rendimiento."""
        # Índice ÚNICO sobre el email: la base de datos es la última línea de
        # defensa contra emails duplicados (más allá de la comprobación en el
        # servicio), evitando condiciones de carrera.
        await self._database[USER_COLLECTION].create_index(
            "email", unique=True, name="uniq_email"
        )

    async def close(self) -> None:
        """Cierra el cliente y resetea el estado. Se llama en el `lifespan`."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("Conexión a MongoDB cerrada")

    @property
    def database(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            raise RuntimeError(
                "La base de datos no está inicializada. "
                "¿Se llamó a MongoConnection.connect() en el lifespan?"
            )
        return self._database


# Instancia única reutilizable en toda la aplicación.
mongo = MongoConnection()


def get_database() -> AsyncIOMotorDatabase:
    """Dependencia de FastAPI: entrega la base de datos activa."""
    return mongo.database
