"""
Schemas de evento: contratos HTTP con VALIDACIÓN ESTRICTA.

Equivalen a lo que en otros stacks sería Zod/Joi/class-validator. Reglas:

- `extra="forbid"` en TODOS los schemas: cualquier campo no declarado (incluido un
  intento de fijar `user_id`, `id` o `created_at`) provoca 422. Esto es clave para
  el aislamiento: el dueño de un evento nunca se acepta desde el cliente.
- Formatos cerrados: `date` = `"YYYY-MM-DD"`, `time` = `"HH:MM"` (24 h),
  `priority` = enum `baja|media|alta`.
- `category` es texto libre pero normalizado (minúsculas, recortado, espacios
  colapsados, sin caracteres de control, ≤40). Los valores de `DEFAULT_CATEGORIES`
  son solo sugerencias.

`EventPublic` define exactamente qué se expone; el `user_id` queda fuera de la
respuesta (principio de mínima exposición, OWASP API3).
"""

import re
from datetime import date as date_type
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.event import Priority

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_WS_RE = re.compile(r"\s+")

_TITLE_MAX = 120
_DESCRIPTION_MAX = 2000
_CATEGORY_MAX = 40

# Campos que, si se envían en un PATCH, no pueden ser nulos.
_NON_NULLABLE_UPDATE_FIELDS = ("title", "date", "time", "category", "priority")


def _has_control_chars(value: str, allow_newlines: bool) -> bool:
    """Detecta caracteres de control (incluye NUL). Permite \\n/\\t si se indica."""
    for char in value:
        if allow_newlines and char in "\n\r\t":
            continue
        if ord(char) < 0x20 or ord(char) == 0x7F:
            return True
    return False


def _clean_title(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("El título no puede estar vacío")
    if _has_control_chars(value, allow_newlines=False):
        raise ValueError("El título contiene caracteres no permitidos")
    return value


def _clean_description(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        # Cadena vacía == sin descripción.
        return None
    if _has_control_chars(value, allow_newlines=True):
        raise ValueError("La descripción contiene caracteres no permitidos")
    return value


def _clean_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not _DATE_RE.match(value):
        raise ValueError("Formato de fecha inválido (se espera YYYY-MM-DD)")
    try:
        date_type.fromisoformat(value)
    except ValueError:
        raise ValueError("La fecha indicada no existe en el calendario")
    return value


def _clean_time(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not _TIME_RE.match(value):
        raise ValueError("Formato de hora inválido (se espera HH:MM en 24 h)")
    return value


def _clean_category(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    # Normalizamos a minúsculas y colapsamos espacios para que los filtros por
    # categoría sean consistentes (misma normalización en el listado).
    value = _WS_RE.sub(" ", value.strip()).lower()
    if not value:
        raise ValueError("La categoría no puede estar vacía")
    if len(value) > _CATEGORY_MAX:
        raise ValueError(f"La categoría no puede superar {_CATEGORY_MAX} caracteres")
    if _has_control_chars(value, allow_newlines=False):
        raise ValueError("La categoría contiene caracteres no permitidos")
    return value


def normalize_category_filter(value: str) -> str:
    """Normaliza el valor de categoría usado como FILTRO del listado."""
    return _WS_RE.sub(" ", value.strip()).lower()


class _EventFields(BaseModel):
    """Campos y validadores comunes a creación y actualización."""

    title: str = Field(..., min_length=1, max_length=_TITLE_MAX)
    description: Optional[str] = Field(default=None, max_length=_DESCRIPTION_MAX)
    date: str
    time: str
    category: str = Field(..., min_length=1, max_length=_CATEGORY_MAX)
    priority: Priority

    @field_validator("title")
    @classmethod
    def _v_title(cls, value: Optional[str]) -> Optional[str]:
        return _clean_title(value)

    @field_validator("description")
    @classmethod
    def _v_description(cls, value: Optional[str]) -> Optional[str]:
        return _clean_description(value)

    @field_validator("date")
    @classmethod
    def _v_date(cls, value: Optional[str]) -> Optional[str]:
        return _clean_date(value)

    @field_validator("time")
    @classmethod
    def _v_time(cls, value: Optional[str]) -> Optional[str]:
        return _clean_time(value)

    @field_validator("category")
    @classmethod
    def _v_category(cls, value: Optional[str]) -> Optional[str]:
        return _clean_category(value)


class EventCreate(_EventFields):
    """Payload de creación de un evento. El dueño lo pone el servidor."""

    model_config = ConfigDict(extra="forbid")


class EventUpdate(_EventFields):
    """Payload de actualización parcial (PATCH). Todos los campos opcionales."""

    model_config = ConfigDict(extra="forbid")

    # Redefinimos los campos como opcionales. Los validadores heredados de
    # `_EventFields` se siguen aplicando cuando el campo está presente.
    title: Optional[str] = Field(default=None, min_length=1, max_length=_TITLE_MAX)
    description: Optional[str] = Field(default=None, max_length=_DESCRIPTION_MAX)
    date: Optional[str] = None
    time: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=_CATEGORY_MAX)
    priority: Optional[Priority] = None

    @model_validator(mode="after")
    def _check_update_payload(self) -> "EventUpdate":
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un campo para actualizar")

        for field_name in _NON_NULLABLE_UPDATE_FIELDS:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"El campo '{field_name}' no puede ser nulo")

        return self


class EventPublic(BaseModel):
    """Representación pública de un evento devuelta por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: Optional[str] = None
    date: str
    time: str
    category: str
    priority: Priority
    created_at: datetime
    updated_at: datetime
