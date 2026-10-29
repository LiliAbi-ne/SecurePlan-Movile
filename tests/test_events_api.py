"""Tests de los endpoints de eventos: CRUD, validación y aislamiento (IDOR)."""

import pytest

from tests.data import VALID_EVENT

BASE = "/api/v1/events"
OTHER_USER_ID = "507f1f77bcf86cd799439022"


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_create_event_returns_public_representation(client, user_factory):
    user = user_factory("a@example.com")
    response = client.post(BASE, headers=user["headers"], json=VALID_EVENT)

    assert response.status_code == 201
    body = response.json()
    assert "user_id" not in body  # no se expone el dueño
    assert body["category"] == "salud"  # normalizada
    assert body["priority"] == "alta"
    assert body["id"]


def test_create_and_read_own_event(client, user_factory):
    user = user_factory("a@example.com")
    event_id = client.post(BASE, headers=user["headers"], json=VALID_EVENT).json()["id"]

    assert client.get(f"{BASE}/{event_id}", headers=user["headers"]).status_code == 200
    listing = client.get(BASE, headers=user["headers"]).json()
    assert len(listing) == 1


def test_update_and_delete_own_event(client, user_factory):
    user = user_factory("a@example.com")
    event_id = client.post(BASE, headers=user["headers"], json=VALID_EVENT).json()["id"]

    updated = client.patch(f"{BASE}/{event_id}", headers=user["headers"], json={"priority": "media"})
    assert updated.status_code == 200
    assert updated.json()["priority"] == "media"

    assert client.delete(f"{BASE}/{event_id}", headers=user["headers"]).status_code == 204
    assert client.get(f"{BASE}/{event_id}", headers=user["headers"]).status_code == 404


def test_user_cannot_access_other_users_event(client, user_factory):
    """IDOR: el usuario B no puede leer, modificar ni borrar el evento de A."""
    user_a = user_factory("a@example.com")
    user_b = user_factory("b@example.com")
    event_id = client.post(BASE, headers=user_a["headers"], json=VALID_EVENT).json()["id"]

    assert client.get(f"{BASE}/{event_id}", headers=user_b["headers"]).status_code == 404
    assert (
        client.patch(
            f"{BASE}/{event_id}", headers=user_b["headers"], json={"title": "hackeado"}
        ).status_code
        == 404
    )
    assert client.delete(f"{BASE}/{event_id}", headers=user_b["headers"]).status_code == 404

    # B no ve el evento de A en su listado...
    assert client.get(BASE, headers=user_b["headers"]).json() == []
    # ...y el evento de A sigue intacto.
    assert client.get(f"{BASE}/{event_id}", headers=user_a["headers"]).status_code == 200


def test_requires_authentication(client):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=VALID_EVENT).status_code == 401


def test_invalid_token_is_rejected(client):
    headers = {"Authorization": "Bearer esto-no-es-un-jwt"}
    assert client.get(BASE, headers=headers).status_code == 401


def test_inactive_user_is_forbidden(client, user_factory):
    user = user_factory("inactivo@example.com", is_active=False)
    assert client.get(BASE, headers=user["headers"]).status_code == 403


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"date": "2026-13-40"}, id="fecha-invalida"),
        pytest.param({"time": "99:99"}, id="hora-invalida"),
        pytest.param({"priority": "urgente"}, id="prioridad-fuera-del-enum"),
        pytest.param({"user_id": OTHER_USER_ID}, id="intento-de-fijar-dueno"),
    ],
)
def test_invalid_payloads_return_422(client, user_factory, override):
    user = user_factory("a@example.com")
    response = client.post(BASE, headers=user["headers"], json={**VALID_EVENT, **override})
    assert response.status_code == 422


def test_malformed_event_id_returns_422(client, user_factory):
    user = user_factory("a@example.com")
    assert client.get(f"{BASE}/no-es-un-id", headers=user["headers"]).status_code == 422


def test_pagination_param_is_validated(client, user_factory):
    user = user_factory("a@example.com")
    assert client.get(f"{BASE}?limit=0", headers=user["headers"]).status_code == 422


def test_categories_endpoint(client, user_factory):
    user = user_factory("a@example.com")
    response = client.get(f"{BASE}/categories", headers=user["headers"])
    assert response.status_code == 200
    assert "personal" in response.json()
