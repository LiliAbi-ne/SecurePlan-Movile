"""
Router de autenticación.

Endpoints:
- POST /auth/register  -> alta de usuario (201).
- POST /auth/login     -> validación de credenciales y emisión de JWT.
- GET  /auth/me        -> ruta protegida de ejemplo que devuelve el usuario actual.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    verify_password,
)
from app.dependencies.auth import get_current_user
from app.models.user import UserModel
from app.schemas.auth import LoginRequest, Token
from app.schemas.common import ErrorResponse
from app.schemas.user import UserCreate, UserPublic
from app.services.user_service import UserService, get_user_service

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description=(
        "Da de alta un usuario. La contraseña debe cumplir la política mínima "
        "(longitud, mayúscula, minúscula, dígito y carácter especial). "
        "El email no puede estar ya registrado."
    ),
    response_description="El usuario creado (sin datos sensibles).",
    operation_id="registerUser",
    responses={
        409: {"model": ErrorResponse, "description": "El email ya está registrado"},
        422: {"model": ErrorResponse, "description": "Datos de entrada inválidos"},
    },
)
async def register(
    payload: UserCreate,
    user_service: UserService = Depends(get_user_service),
) -> UserModel:
    # Comprobación previa para dar un 409 claro...
    if await user_service.get_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )

    try:
        # ...y, aun así, capturamos la colisión del índice único por si dos
        # registros con el mismo email ocurren en paralelo (condición de carrera).
        return await user_service.create(payload)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión y obtener un access token",
    description=(
        "Valida las credenciales y devuelve un JWT de acceso. Si el email no "
        "existe o la contraseña no coincide, responde 401 con un mensaje genérico "
        "(no revela cuál de los dos campos falló)."
    ),
    response_description="El token de acceso y su tiempo de vida en segundos.",
    operation_id="loginUser",
    responses={
        401: {"model": ErrorResponse, "description": "Email o contraseña incorrectos"},
        403: {"model": ErrorResponse, "description": "La cuenta está desactivada"},
        422: {"model": ErrorResponse, "description": "Datos de entrada inválidos"},
    },
)
async def login(
    payload: LoginRequest,
    user_service: UserService = Depends(get_user_service),
) -> Token:
    user = await user_service.get_by_email(payload.email)

    # Contra un hash señuelo cuando el usuario no existe: el tiempo de respuesta
    # no revela si el email está registrado o no.
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_ok = await verify_password(payload.password, password_hash)

    if user is None or not password_ok:
        # Mensaje genérico: nunca revelamos cuál de los dos campos falló.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está desactivada",
        )

    access_token = create_access_token(subject=user.id)
    return Token(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Obtener el usuario autenticado",
    description=(
        "Devuelve los datos públicos del usuario dueño del token. Requiere "
        "`Authorization: Bearer <token>`."
    ),
    response_description="El usuario autenticado.",
    operation_id="readCurrentUser",
    responses={
        401: {"model": ErrorResponse, "description": "Token ausente o inválido"},
        403: {"model": ErrorResponse, "description": "La cuenta está desactivada"},
    },
)
async def read_current_user(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    return current_user
