"""Tests del `EventService`: aislamiento por usuario (IDOR), filtros y paginación."""

from bson import ObjectId

from app.models.event import EVENT_COLLECTION, Priority
from app.schemas.event import EventCreate, EventUpdate
from app.services.event_service import EventService
from tests.data import VALID_EVENT
from tests.fakes import InMemoryDatabase

USER_A = "507f1f77bcf86cd799439011"
USER_B = "507f1f77bcf86cd799439022"


def _service(database: InMemoryDatabase) -> EventService:
    return EventService(database)


async def test_create_forces_owner_from_argument(database):
    service = _service(database)
    event = await service.create(USER_A, EventCreate(**VALID_EVENT))

    stored = database[EVENT_COLLECTION].documents[0]
    assert event.user_id == USER_A
    assert stored["user_id"] == ObjectId(USER_A)
    # `priority` se persiste como texto (no como enum).
    assert stored["priority"] == "alta"


async def test_list_only_returns_own_events(database):
    service = _service(database)
    await service.create(USER_A, EventCreate(**VALID_EVENT))
    await service.create(USER_B, EventCreate(**{**VALID_EVENT, "title": "De B"}))

    events_a = await service.list_for_user(USER_A)
    assert len(events_a) == 1
    assert events_a[0].user_id == USER_A

    events_b = await service.list_for_user(USER_B)
    assert len(events_b) == 1
    assert events_b[0].user_id == USER_B


async def test_get_update_delete_are_scoped_to_owner(database):
    service = _service(database)
    event = await service.create(USER_A, EventCreate(**VALID_EVENT))

    # Otro usuario no puede leer, modificar ni borrar.
    assert await service.get_for_user(event.id, USER_B) is None
    assert await service.update_for_user(event.id, USER_B, EventUpdate(priority="media")) is None
    assert await service.delete_for_user(event.id, USER_B) is False

    # El dueño sí.
    assert (await service.get_for_user(event.id, USER_A)).id == event.id
    updated = await service.update_for_user(event.id, USER_A, EventUpdate(category="Ocio"))
    assert updated.category == "ocio"
    assert updated.priority == Priority.alta  # no cambió
    assert await service.delete_for_user(event.id, USER_A) is True
    assert await service.get_for_user(event.id, USER_A) is None


async def test_filters_and_pagination(database):
    service = _service(database)
    for index in range(5):
        await service.create(
            USER_A,
            EventCreate(
                **{
                    **VALID_EVENT,
                    "date": f"2026-11-0{index + 1}",
                    "category": "trabajo" if index < 3 else "ocio",
                    "priority": "baja" if index % 2 == 0 else "alta",
                }
            ),
        )

    assert len(await service.list_for_user(USER_A)) == 5
    assert len(await service.list_for_user(USER_A, category="trabajo")) == 3
    assert len(await service.list_for_user(USER_A, priority=Priority.alta)) == 2
    assert len(await service.list_for_user(USER_A, date_from="2026-11-03")) == 3
    assert len(await service.list_for_user(USER_A, date_to="2026-11-02")) == 2

    # Paginación
    page = await service.list_for_user(USER_A, limit=2)
    assert len(page) == 2
    assert len(await service.list_for_user(USER_A, limit=2, offset=4)) == 1

    # Orden por fecha ascendente
    dates = [event.date for event in await service.list_for_user(USER_A)]
    assert dates == sorted(dates)


async def test_invalid_id_never_reaches_query(database):
    service = _service(database)
    assert await service.get_for_user("no-es-un-objectid", USER_A) is None
    assert await service.update_for_user("123", USER_A, EventUpdate(priority="baja")) is None
    assert await service.delete_for_user("123", USER_A) is False
