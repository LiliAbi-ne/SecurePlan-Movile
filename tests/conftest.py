"""Fixtures compartidas de la suite.

Estrategia: en vez de levantar un MongoDB real, se sobrescribe la dependencia
`get_database` para inyectar una base en memoria (`tests/fakes.py`). Los tokens
son JWT REALES (`create_access_token`) y el `get_current_user` real resuelve el
usuario contra esa base, así que se ejercita toda la cadena (auth + router +
servicio + validación) sin infraestructura externa.

Nota: el `TestClient` se usa SIN `with`, por lo que NO se ejecuta el `lifespan`
(y por tanto no se intenta abrir conexión a MongoDB real).
"""

import os

# Debe fijarse ANTES de importar la app: `security.py` construye `Settings` al
# importarse y exige un JWT_SECRET_KEY válido (>= 32 caracteres).
os.environ["JWT_SECRET_KEY"] = "test-secret-key-" + "x" * 32
os.environ.setdefault("ENVIRONMENT", "development")

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import get_database  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from tests.fakes import InMemoryDatabase  # noqa: E402


@pytest.fixture
def database() -> InMemoryDatabase:
    """Base en memoria fresca por test (aislamiento entre tests)."""
    return InMemoryDatabase()


@pytest.fixture
def client(database: InMemoryDatabase) -> TestClient:
    """Cliente HTTP con `get_database` apuntando a la base en memoria."""
    app.dependency_overrides[get_database] = lambda: database
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_factory(database: InMemoryDatabase):
    """
    Crea usuarios y devuelve su id + cabecera Authorization con un JWT válido.

    Uso: `user = user_factory("a@example.com")` -> `user["headers"]`.
    """

    def _factory(email: str, is_active: bool = True) -> dict:
        now = datetime.now(timezone.utc)
        user_id = database["users"].seed(
            {
                "email": email,
                "password_hash": "no-usado-en-estos-tests",
                "is_active": is_active,
                "created_at": now,
                "updated_at": now,
            }
        )
        token = create_access_token(subject=str(user_id))
        return {"id": str(user_id), "headers": {"Authorization": f"Bearer {token}"}}

    return _factory
