"""Tests de los schemas de evento: validación estricta de entrada."""

import pytest
from pydantic import ValidationError

from app.schemas.event import EventCreate, EventUpdate
from tests.data import VALID_EVENT


def test_create_accepts_valid_payload_and_normalizes():
    event = EventCreate(**VALID_EVENT)
    # La categoría llega como "Salud" y debe normalizarse a minúsculas.
    assert event.category == "salud"
    assert event.priority.value == "alta"


def test_create_empty_description_becomes_none():
    event = EventCreate(**{**VALID_EVENT, "description": ""})
    assert event.description is None


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"date": "2026-13-40"}, id="fecha-inexistente"),
        pytest.param({"date": "05/11/2026"}, id="fecha-formato-invalido"),
        pytest.param({"time": "25:99"}, id="hora-invalida"),
        pytest.param({"time": "9:30"}, id="hora-sin-cero-izquierda"),
        pytest.param({"priority": "urgente"}, id="prioridad-fuera-del-enum"),
        pytest.param({"title": "   "}, id="titulo-vacio"),
        pytest.param({"title": "a\nb"}, id="titulo-con-salto-de-linea"),
        pytest.param({"title": "x" * 121}, id="titulo-demasiado-largo"),
        pytest.param({"category": "   "}, id="categoria-vacia"),
        pytest.param({"category": "a" * 41}, id="categoria-demasiado-larga"),
        pytest.param({"user_id": "507f1f77bcf86cd799439011"}, id="campo-extra-user_id"),
        pytest.param({"_id": "507f1f77bcf86cd799439011"}, id="campo-extra-_id"),
    ],
)
def test_create_rejects_invalid_payloads(override):
    with pytest.raises(ValidationError):
        EventCreate(**{**VALID_EVENT, **override})


def test_update_partial_is_valid():
    update = EventUpdate(priority="media")
    assert update.priority.value == "media"


def test_update_empty_payload_is_rejected():
    with pytest.raises(ValidationError):
        EventUpdate()


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"title": None}, id="title-null"),
        pytest.param({"date": None}, id="date-null"),
        pytest.param({"time": None}, id="time-null"),
        pytest.param({"category": None}, id="category-null"),
        pytest.param({"priority": None}, id="priority-null"),
        pytest.param({"priority": "urgente"}, id="prioridad-invalida"),
        pytest.param({"user_id": "507f1f77bcf86cd799439011"}, id="campo-extra"),
    ],
)
def test_update_rejects_invalid_payloads(override):
    with pytest.raises(ValidationError):
        EventUpdate(**override)


def test_update_allows_clearing_description_with_null():
    update = EventUpdate(description=None)
    assert update.model_dump(exclude_unset=True) == {"description": None}
