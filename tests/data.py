"""Datos de ejemplo reutilizados por los tests."""

# Payload válido de evento. `category` en mayúsculas a propósito: el schema debe
# normalizarla a minúsculas ("salud").
VALID_EVENT = {
    "title": "Cita dentista",
    "description": "Llevar radiografía",
    "date": "2026-11-05",
    "time": "10:30",
    "category": "Salud",
    "priority": "alta",
}
