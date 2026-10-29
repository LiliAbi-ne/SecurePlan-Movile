# Agenda API (Sprint 2)

Backend desacoplado para la aplicación móvil de gestión del tiempo y productividad
(**Agenda**). Implementa la base móvil, la arquitectura modular, la autenticación
segura y el **CRUD de eventos** con **FastAPI** + **MongoDB** (Motor, asíncrono).

## Stack

- **FastAPI** (asíncrono nativo, `async/await`)
- **MongoDB** con **Motor** (driver asíncrono)
- **Pydantic v2** + **pydantic-settings** (validación estricta y config)
- **passlib + Argon2** (hashing de contraseñas)
- **PyJWT** (tokens JWT firmados)

## Estructura de carpetas

```
CALENDARIO/
├── app/
│   ├── __init__.py
│   ├── main.py                  # App FastAPI: lifespan, middleware, handlers
│   ├── core/                   # Infraestructura transversal
│   │   ├── config.py           # Settings (pydantic-settings, singleton con lru_cache)
│   │   ├── database.py         # Conexión MongoDB Singleton (patrón + lifespan)
│   │   └── security.py         # Hashing Argon2 y creación/validación de JWT
│   ├── models/                 # Representación de documentos (capa de datos)
│   │   ├── common.py           # PyObjectId (tipo BSON reutilizable)
│   │   ├── user.py             # UserModel + nombre de colección
│   │   └── event.py            # EventModel + Priority + categorías sugeridas
│   ├── schemas/                # Contratos de entrada/salida de la API (Pydantic)
│   │   ├── user.py             # UserCreate, UserPublic
│   │   ├── auth.py             # LoginRequest, Token
│   │   └── event.py            # EventCreate, EventUpdate, EventPublic
│   ├── services/               # Lógica de negocio / acceso a datos
│   │   ├── user_service.py     # CRUD de usuarios + dependencia get_user_service
│   │   └── event_service.py    # CRUD de eventos (scoped por usuario) + get_event_service
│   ├── dependencies/           # Dependencias reutilizables de FastAPI
│   │   └── auth.py             # get_current_user (protección de rutas)
│   └── routers/                # Endpoints HTTP
│       ├── auth.py             # /auth/register, /auth/login, /auth/me
│       └── events.py           # /events (CRUD protegido)
├── tests/                      # Suite de tests (pytest) + doble en memoria de Mongo
│   ├── conftest.py             # Fixtures (client, database, user_factory)
│   ├── fakes.py                # Doble en memoria que respeta los filtros
│   ├── data.py                 # Datos de ejemplo
│   ├── test_schemas.py         # Validación estricta de entrada
│   ├── test_event_service.py   # Servicio: filtros, paginación y scoping por dueño
│   └── test_events_api.py      # Endpoints: CRUD, errores y aislamiento (IDOR)
├── pytest.ini                  # Configuración de pytest
├── requirements-dev.txt        # Dependencias de desarrollo/test
├── .env.example                # Plantilla de variables de entorno
├── .gitignore
├── openapi.yml                 # Contrato OpenAPI generado (copia estática para el front)
├── requirements.txt
└── README.md
```

## Requisitos

- **Python 3.14** (obligatorio). Todas las dependencias publican wheels para
  CPython 3.14, así que la instalación no compila nada (sin Rust ni toolchain C).

## Puesta en marcha

### 1. Crear entorno e instalar dependencias

Comprueba que `python` es la versión 3.14 (`python --version`):

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Genera una clave JWT robusta:
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pega el valor generado en `JWT_SECRET_KEY` dentro de `.env`.

### 3. Arrancar la API

```bash
uvicorn app.main:app --reload
```

- Documentación interactiva (solo en `development`): http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

### 4. Probar el flujo de autenticación

```bash
# Registro
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"S3gur4-Password!"}'

# Login (devuelve el access_token)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"S3gur4-Password!"}'

# Ruta protegida
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## Eventos (Sprint 2)

CRUD de actividades diarias. **Todas** las rutas requieren `Authorization: Bearer
<token>` (protegidas por la dependencia `get_current_user`).

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/events/categories` | Categorías sugeridas (presets) |
| POST | `/events` | Crear un evento (201) |
| GET | `/events` | Listar mis eventos con filtros y paginación |
| GET | `/events/{id}` | Obtener un evento propio |
| PATCH | `/events/{id}` | Actualizar parcialmente un evento propio |
| DELETE | `/events/{id}` | Eliminar un evento propio (204) |

Campos de un evento: `title` (1–120), `description` opcional (≤2000),
`date` (`YYYY-MM-DD`), `time` (`HH:MM`, 24 h), `category` (texto libre normalizado,
≤40; se sugieren `personal`, `trabajo`, `estudio`, `salud`, `ocio`, `otro`) y
`priority` (`baja` | `media` | `alta`).

Filtros del listado (`GET /events`): `category`, `priority`, `date_from`,
`date_to`, `limit` (1–100, def. 20) y `offset` (≥0).

La documentación interactiva (`/docs` y `/redoc`) describe cada endpoint con sus
parámetros, las respuestas de error (401/403/404/409/422) y ejemplos de
petición/respuesta; el esquema OpenAPI completo se sirve en `/openapi.json`.

Para consumir el contrato sin levantar el servidor —generar un cliente o los
tipos del frontend, mocks, validar en CI— hay una copia estática versionada en
[`openapi.yml`](./openapi.yml). Es un **artefacto generado** a partir del código
(FastAPI es *code-first*), así que **hay que regenerarlo** cuando cambien las
rutas o los schemas:

```bash
python scripts/export_openapi.py
```

```bash
# Crear
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"title":"Cita dentista","description":"Llevar radiografía","date":"2026-11-05","time":"10:30","category":"salud","priority":"alta"}'

# Listar (filtros + paginación)
curl "http://localhost:8000/api/v1/events?priority=alta&date_from=2026-11-01&limit=10" \
  -H "Authorization: Bearer <access_token>"

# Obtener / actualizar parcial / eliminar
curl http://localhost:8000/api/v1/events/<event_id> -H "Authorization: Bearer <access_token>"
curl -X PATCH http://localhost:8000/api/v1/events/<event_id> \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"priority":"media"}'
curl -X DELETE http://localhost:8000/api/v1/events/<event_id> -H "Authorization: Bearer <access_token>"
```

## Tests

Suite con **pytest** que corre **sin necesidad de MongoDB**: usa un doble en
memoria (`tests/fakes.py`) que respeta los filtros, incluido el `user_id`, por lo
que el aislamiento anti-IDOR se valida de verdad.

```bash
pip install -r requirements-dev.txt
pytest            # o:  pytest -q
```

Cubre: validación estricta de los schemas, el servicio (filtros, paginación y
scoping por dueño) y los endpoints (CRUD, 401/403/422 y aislamiento entre
usuarios).

## Notas de seguridad aplicadas (OWASP API Top 10)

- **API1 (BOLA / IDOR):** toda consulta a `events` filtra por el `user_id` del token;
  un evento ajeno responde `404` (igual que uno inexistente) para no revelar su
  existencia, y el dueño nunca se acepta desde el cliente (`extra="forbid"`).
- **API2 (Broken Authentication):** contraseñas con Argon2, JWT firmado con `exp`/`iss`/`nbf`,
  validación de credenciales con mensaje genérico (evita enumeración de usuarios).
- **API3 (Excessive Data Exposure):** el `password_hash` nunca se serializa en respuestas
  y `EventPublic` no expone `user_id`.
- **API8 (Injection):** validación estricta de entrada con Pydantic; los `id` se validan
  como `ObjectId` y las queries se construyen solo con campos tipados (sin concatenación
  ni diccionarios crudos del cliente).
- **API10 / manejo de errores:** un handler global oculta las trazas internas y registra
  el error en el servidor, devolviendo un `500` genérico al cliente.
- **Cabeceras de seguridad** añadidas por middleware (`nosniff`, `X-Frame-Options`, HSTS).
- **CORS:** lista blanca configurable, nunca `*` en producción.
