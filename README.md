# Agenda API (Sprint 1)

Backend desacoplado para la aplicación móvil de gestión del tiempo y productividad
(**Agenda**). Implementa la base móvil, la arquitectura modular y la autenticación
segura con **FastAPI** + **MongoDB** (Motor, asíncrono).

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
│   │   └── user.py             # UserModel + PyObjectId + nombre de colección
│   ├── schemas/                # Contratos de entrada/salida de la API (Pydantic)
│   │   ├── user.py             # UserCreate, UserPublic
│   │   └── auth.py             # LoginRequest, Token
│   ├── services/               # Lógica de negocio / acceso a datos
│   │   └── user_service.py     # CRUD de usuarios + dependencia get_user_service
│   ├── dependencies/           # Dependencias reutilizables de FastAPI
│   │   └── auth.py             # get_current_user (protección de rutas)
│   └── routers/                # Endpoints HTTP
│       └── auth.py             # /auth/register, /auth/login, /auth/me
├── tests/                      # (pendiente para siguientes sprints)
├── .env.example                # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt
└── README.md
```

## Puesta en marcha

### 1. Requisitos

- **Python 3.11 o 3.12.** Evita 3.13+ / 3.14: `passlib` aún no es compatible con
  esos intérpretes (el módulo estándar `crypt` fue eliminado).
- Una instancia de MongoDB (local o Atlas).

> **Si tu único Python es 3.13+** (por ejemplo 3.14), crea un entorno 3.12 con conda:
>
> ```bash
> conda create -n agenda python=3.12 -y
> conda activate agenda
> ```
>
> Si prefieres no aceptar los Términos de Servicio de Anaconda, usa conda-forge:
>
> ```bash
> conda create -n agenda python=3.12 -c conda-forge --override-channels -y
> ```

### 2. Crear entorno e instalar dependencias

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Genera una clave JWT robusta:
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pega el valor generado en `JWT_SECRET_KEY` dentro de `.env`.

### 4. Arrancar la API

```bash
uvicorn app.main:app --reload
```

- Documentación interactiva (solo en `development`): http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

### 5. Probar el flujo de autenticación

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

## Notas de seguridad aplicadas (OWASP API Top 10)

- **API1/API2 (Broken Auth):** contraseñas con Argon2, JWT firmado con `exp`/`iss`/`nbf`,
  validación de credenciales con mensaje genérico (evita enumeración de usuarios).
- **API3 (Excessive Data Exposure):** el `password_hash` nunca se serializa en respuestas.
- **API8 (Injection):** validación estricta de entrada con Pydantic; sin construcción de
  queries con concatenación de strings.
- **API10 / manejo de errores:** un handler global oculta las trazas internas y registra
  el error en el servidor, devolviendo un `500` genérico al cliente.
- **Cabeceras de seguridad** añadidas por middleware (`nosniff`, `X-Frame-Options`, HSTS).
- **CORS:** lista blanca configurable, nunca `*` en producción.
