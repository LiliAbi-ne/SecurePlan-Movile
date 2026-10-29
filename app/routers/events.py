"""
Router de eventos (actividades diarias).

Todos los endpoints quedan protegidos: el router declara la dependencia
`get_current_user` a nivel de router (defensa en profundidad) y cada handler la
vuelve a pedir para disponer del usuario actual. FastAPI cachea la dependencia,
así que no se resuelve dos veces por petición.

Aislamiento (anti-IDOR): cada handler opera SIEMPRE sobre el `user_id` del token.
Un evento que existe pero pertenece a otro usuario se trata como inexistente
(404), igual que uno que no existe, para no filtrar su existencia.

Endpoints:
- GET    /events/categories   -> categorías sugeridas (presets).
- POST   /events              -> crear (201).
- GET    /events              -> listar con filtros y paginación.
- GET    /events/{id}         -> obtener uno propio.
- PATCH  /events/{id}         -> actualizar parcialmente uno propio.
- DELETE /events/{id}         -> eliminar uno propio (204).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.models.common import PyObjectId
from app.models.event import DEFAULT_CATEGORIES, Priority
from app.models.user import UserModel
from app.schemas.common import ErrorResponse
from app.schemas.event import EventCreate, EventPublic, EventUpdate
from app.services.event_service import EventService, get_event_service

router = APIRouter(
    prefix="/events",
    tags=["Eventos"],
    dependencies=[Depends(get_current_user)],
)

# --- Respuestas de error reutilizables (documentación OpenAPI) ---------------
# Comunes a todos los endpoints porque el router exige autenticación.
_AUTH_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Token ausente o inválido"},
    403: {"model": ErrorResponse, "description": "La cuenta está desactivada"},
}
_VALIDATION_RESPONSE = {
    422: {"model": ErrorResponse, "description": "Datos de entrada inválidos"},
}
_NOT_FOUND_RESPONSE = {
    404: {"model": ErrorResponse, "description": "Evento no encontrado"}
}


def _not_found_exception() -> HTTPException:
    # Nueva instancia por llamada (no se reutilizan excepciones entre peticiones).
    # Mismo mensaje para "no existe" y "es de otro": no revelamos existencia.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Evento no encontrado",
    )


# NOTA: esta ruta debe declararse ANTES de "/{event_id}" para que el literal
# "categories" no sea capturado como un id.
@router.get(
    "/categories",
    response_model=list[str],
    summary="Categorías sugeridas",
    description=(
        "Devuelve las categorías preset que la app ofrece como atajo. No es una "
        "lista cerrada: el campo `category` admite cualquier texto válido."
    ),
    response_description="Lista de categorías sugeridas.",
    operation_id="listEventCategories",
    responses={**_AUTH_RESPONSES},
)
async def list_categories() -> list[str]:
    return list(DEFAULT_CATEGORIES)


@router.post(
    "",
    response_model=EventPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un evento",
    description=(
        "Crea un evento cuyo dueño es SIEMPRE el usuario del token. Cualquier "
        "intento de fijar el dueño (`user_id`) u otros campos internos se rechaza "
        "con 422."
    ),
    response_description="El evento creado.",
    operation_id="createEvent",
    responses={**_AUTH_RESPONSES, **_VALIDATION_RESPONSE},
)
async def create_event(
    payload: EventCreate,
    current_user: UserModel = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service),
) -> EventPublic:
    return await event_service.create(current_user.id, payload)


@router.get(
    "",
    response_model=list[EventPublic],
    summary="Listar mis eventos",
    description=(
        "Lista los eventos del usuario autenticado, ordenados por fecha y hora "
        "ascendentes. Admite filtros por `category`, `priority` y rango de fechas "
        "(`date_from`/`date_to`), además de paginación con `limit`/`offset`."
    ),
    response_description="Los eventos del usuario que cumplen los filtros.",
    operation_id="listEvents",
    responses={**_AUTH_RESPONSES, **_VALIDATION_RESPONSE},
)
async def list_events(
    current_user: UserModel = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service),
    category: Optional[str] = Query(default=None, max_length=40),
    priority: Optional[Priority] = Query(default=None),
    date_from: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[EventPublic]:
    return await event_service.list_for_user(
        current_user.id,
        category=category,
        priority=priority,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{event_id}",
    response_model=EventPublic,
    summary="Obtener un evento propio",
    description=(
        "Devuelve un evento del usuario. Si el evento no existe o pertenece a otro "
        "usuario se responde 404 en ambos casos, para no revelar su existencia "
        "(mitigación de IDOR / OWASP API1 BOLA)."
    ),
    response_description="El evento solicitado.",
    operation_id="getEvent",
    responses={
        **_AUTH_RESPONSES,
        **_NOT_FOUND_RESPONSE,
        **_VALIDATION_RESPONSE,
    },
)
async def get_event(
    event_id: PyObjectId,
    current_user: UserModel = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service),
) -> EventPublic:
    event = await event_service.get_for_user(event_id, current_user.id)
    if event is None:
        raise _not_found_exception()
    return event


@router.patch(
    "/{event_id}",
    response_model=EventPublic,
    summary="Actualizar un evento propio",
    description=(
        "Actualización parcial: solo se modifican los campos enviados (al menos "
        "uno). `description: null` borra la descripción; el resto de campos no "
        "pueden ser nulos. Un evento ajeno responde 404, igual que uno inexistente."
    ),
    response_description="El evento actualizado.",
    operation_id="updateEvent",
    responses={
        **_AUTH_RESPONSES,
        **_NOT_FOUND_RESPONSE,
        **_VALIDATION_RESPONSE,
    },
)
async def update_event(
    event_id: PyObjectId,
    payload: EventUpdate,
    current_user: UserModel = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service),
) -> EventPublic:
    event = await event_service.update_for_user(event_id, current_user.id, payload)
    if event is None:
        raise _not_found_exception()
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un evento propio",
    description=(
        "Elimina un evento del usuario. Responde 204 sin cuerpo si lo borra, o "
        "404 si no existe o pertenece a otro usuario."
    ),
    response_description="Evento eliminado (sin cuerpo).",
    operation_id="deleteEvent",
    responses={
        **_AUTH_RESPONSES,
        **_NOT_FOUND_RESPONSE,
        **_VALIDATION_RESPONSE,
    },
)
async def delete_event(
    event_id: PyObjectId,
    current_user: UserModel = Depends(get_current_user),
    event_service: EventService = Depends(get_event_service),
) -> None:
    deleted = await event_service.delete_for_user(event_id, current_user.id)
    if not deleted:
        raise _not_found_exception()
