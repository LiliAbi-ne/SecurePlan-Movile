"""
Seguridad: hashing de contraseñas (Argon2) y tokens JWT.

Decisiones de diseño relevantes:
- Argon2id es el algoritmo de hashing de contraseñas recomendado hoy (ganador de
  la Password Hashing Competition) y resistente a ataques con GPU.
- El hashing es COMPUTACIONALMENTE COSTOSO (por diseño). Ejecutarlo en el bucle
  de eventos bloquearía todas las peticiones concurrentes; por eso lo derivamos
  a un hilo del threadpool con `run_in_threadpool`, manteniendo el `async/await`
  nativo de FastAPI sin regalar el rendimiento.
- Los JWT se firman con HMAC-SHA256 e incluyen `exp`, `iat`, `nbf`, `iss` y un
  campo `type` para poder distinguir futuros tipos de token (p. ej. refresh).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

settings = get_settings()

# Contexto de hashing. `argon2` como esquema principal; `deprecated="auto"` deja
# la puerta abierta a migrar esquemas antiguos automáticamente si algún día se
# cambia el algoritmo.
_pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=settings.ARGON2_TIME_COST,
    argon2__memory_cost=settings.ARGON2_MEMORY_COST,
    argon2__parallelism=settings.ARGON2_PARALLELISM,
)

# Tipo de token, para validar que un access token no se use como refresh, etc.
_ACCESS_TOKEN_TYPE = "access"


# --------------------------------------------------------------------------- #
# Contraseñas
# --------------------------------------------------------------------------- #
def _hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def _verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except ValueError:
        # Hash con formato inválido/corrupto: se trata como no verificado.
        return False


async def hash_password(password: str) -> str:
    """Hashea una contraseña sin bloquear el event loop."""
    return await run_in_threadpool(_hash_password, password)


async def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica una contraseña sin bloquear el event loop."""
    return await run_in_threadpool(_verify_password, plain_password, password_hash)


# Hash señuelo: se verifica contra él cuando el email no existe, para que el
# login tarde lo mismo exista o no el usuario (mitiga la enumeración de cuentas
# por análisis de tiempos de respuesta).
DUMMY_PASSWORD_HASH = _hash_password("timing-attack-mitigation-placeholder")


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Genera un JWT firmado para el `subject` (normalmente el id del usuario).

    Solo se incluyen claims mínimos: nada de datos sensibles en el payload,
    porque el token es legible por cualquiera (firmado, pero NO cifrado).
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "type": _ACCESS_TOKEN_TYPE,
        "iss": settings.JWT_ISSUER,
        "iat": now,
        "nbf": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decodifica y VALIDA un JWT.

    Verifica firma, expiración (`exp`), emisor (`iss`) y exige la presencia de
    los claims obligatorios. Lanza `jwt.InvalidTokenError` si algo no cuadra.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        options={"require": ["exp", "iat", "nbf", "sub", "iss"]},
    )
