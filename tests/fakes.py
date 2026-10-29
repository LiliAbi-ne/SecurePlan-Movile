"""Doble en memoria de MongoDB para los tests.

Implementa solo el subconjunto que usa la aplicación (`insert_one`, `find` con
`sort`/`skip`/`limit`, `find_one`, `find_one_and_update`, `delete_one`) y, muy
importante, **respetando los filtros** (incluido el `user_id`). Gracias a esto los
tests de aislamiento (IDOR) son significativos: si el servicio olvidara filtrar
por dueño, los tests fallarían.

Así la suite corre sin necesitar un servidor MongoDB real.
"""

from bson import ObjectId


def _matches(document: dict, query: dict) -> bool:
    """Comprueba si un documento satisface un filtro (igualdad y rangos $gte/$lte)."""
    for field, condition in query.items():
        if isinstance(condition, dict) and any(str(k).startswith("$") for k in condition):
            value = document.get(field)
            if "$gte" in condition and not (value is not None and value >= condition["$gte"]):
                return False
            if "$lte" in condition and not (value is not None and value <= condition["$lte"]):
                return False
            if "$ne" in condition and document.get(field) == condition["$ne"]:
                return False
        elif document.get(field) != condition:
            return False
    return True


class InsertResult:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class DeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class InMemoryCursor:
    """Cursor mínimo: soporta `sort`, `skip`, `limit` e iteración asíncrona."""

    def __init__(self, documents: list[dict]) -> None:
        self._documents = list(documents)
        self._skip = 0
        self._limit: int | None = None

    def sort(self, keys) -> "InMemoryCursor":
        # Orden multi-clave estable: aplicar de la última clave a la primera.
        for field, direction in reversed(list(keys)):
            self._documents.sort(key=lambda d: d.get(field), reverse=direction < 0)
        return self

    def skip(self, count: int) -> "InMemoryCursor":
        self._skip = count
        return self

    def limit(self, count: int) -> "InMemoryCursor":
        self._limit = count
        return self

    def _page(self) -> list[dict]:
        documents = self._documents[self._skip :]
        if self._limit is not None:
            documents = documents[: self._limit]
        return documents

    def __aiter__(self) -> "InMemoryCursor":
        self._iterator = iter(self._page())
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class InMemoryCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    def seed(self, document: dict) -> ObjectId:
        """Inserta de forma SÍNCRONA (para preparar datos en las fixtures)."""
        stored = dict(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return stored["_id"]

    async def insert_one(self, document: dict) -> InsertResult:
        return InsertResult(self.seed(document))

    def find(self, query: dict) -> InMemoryCursor:
        return InMemoryCursor([d for d in self.documents if _matches(d, query)])

    async def find_one(self, query: dict) -> dict | None:
        for document in self.documents:
            if _matches(document, query):
                return document
        return None

    async def find_one_and_update(self, query: dict, update: dict, return_document=None):
        for document in self.documents:
            if _matches(document, query):
                document.update(update.get("$set", {}))
                return document
        return None

    async def delete_one(self, query: dict) -> DeleteResult:
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                del self.documents[index]
                return DeleteResult(1)
        return DeleteResult(0)


class InMemoryDatabase:
    """Se comporta como `AsyncIOMotorDatabase[name] -> colección`."""

    def __init__(self) -> None:
        self._collections: dict[str, InMemoryCollection] = {}

    def __getitem__(self, name: str) -> InMemoryCollection:
        return self._collections.setdefault(name, InMemoryCollection())
