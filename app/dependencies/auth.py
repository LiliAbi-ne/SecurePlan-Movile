"""
Dependencia de autenticación: protege rutas verificando el JWT.

Cualquier endpoint que declare `current_user: UserModel = Depends(get_current_user)`
queda automáticamente protegido. Si el token falta, es inválido, está expirado o
el usuario no existe/está inactivo, se responde 401/403 con un mensaje genérico.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.security import decode_token
from app.models.user import UserModel
from app.services.user_service import UserService, get_user_service

settings = get_settings()

# `tokenUrl` es solo informativo para la UI de Swagger (botón "Authorize").
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def _credentials_exception() -> HTTPException:
    # Se construye una excepción nueva por llamada (evita reutilizar instancias).
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> UserModel:
    """Resuelve el usuario autenticado a partir del token Bearer."""
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        # Cualquier fallo de firma/expiración/formato colapsa en el mismo 401.
        raise _credentials_exception()

    # Solo aceptamos tokens de tipo "access" en rutas de acceso.
    if payload.get("type") != "access":
        raise _credentials_exception()

    user_id = payload.get("sub")
    if not user_id:
        raise _credentials_exception()

    user = await user_service.get_by_id(user_id)
    if user is None:
        raise _credentials_exception()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada",
        )

    return user
