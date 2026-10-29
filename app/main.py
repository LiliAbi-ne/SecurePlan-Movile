"""
Punto de entrada de la aplicación FastAPI.

Aquí se orquesta todo:
- `lifespan`: abre/cierra la conexión Singleton a MongoDB.
- Middleware de CORS y cabeceras de seguridad.
- Handlers globales que evitan filtrar errores internos (OWASP).
- Registro de routers bajo el prefijo de versión de la API.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import mongo
from app.routers import auth, events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Arranque ---
    await mongo.connect()
    logger.info("%s iniciada (entorno=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    try:
        yield
    finally:
        # --- Apagado ---
        await mongo.close()
        logger.info("%s detenida", settings.APP_NAME)


# La documentación interactiva se deshabilita en producción.
_docs_enabled = not settings.is_production

# Descripción global que encabeza la documentación interactiva (/docs y /redoc).
_DESCRIPTION = """
API desacoplada para la aplicación móvil de gestión del tiempo **Agenda**.

## Autenticación
Las rutas de **Eventos** requieren un token JWT. Obtén uno en
`POST /api/v1/auth/login` y pulsa el botón **Authorize** para enviarlo como
`Authorization: Bearer <token>`.

## Aislamiento por usuario
Cada usuario solo puede ver y gestionar **sus propios** eventos. Un evento ajeno
se responde como inexistente (404) para no revelar su existencia (mitigación de
IDOR / OWASP API1 BOLA).
"""

# Descripciones de los tags usados por los routers (orden = orden en /docs).
_TAGS_METADATA = [
    {"name": "Sistema", "description": "Estado del servicio (health check)."},
    {
        "name": "Autenticación",
        "description": (
            "Registro, inicio de sesión y datos del usuario autenticado. "
            "Las contraseñas se almacenan con Argon2 y los tokens son JWT firmados."
        ),
    },
    {
        "name": "Eventos",
        "description": (
            "CRUD de actividades diarias. Todas las rutas requieren autenticación "
            "y están acotadas al usuario del token (anti-IDOR)."
        ),
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=_DESCRIPTION,
    openapi_tags=_TAGS_METADATA,
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS con lista blanca. `allow_credentials` se mantiene en True, por lo que los
# orígenes deben ser explícitos (nunca "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Añade cabeceras de endurecimiento recomendadas (OWASP)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains"
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Devuelve un 422 limpio sin exponer detalles internos del esquema."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Datos de entrada inválidos"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Captura cualquier error no controlado.

    La traza completa se registra en el servidor; al cliente solo le llega un
    mensaje genérico, evitando fugas de información (nombres de tablas, rutas,
    versiones de librerías, etc.).
    """
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )


# --- Routers ---
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)


# --- Endpoint de salud (útil para orquestadores / load balancers) ---
@app.get(
    f"{settings.API_V1_PREFIX}/health",
    tags=["Sistema"],
    summary="Health check",
    description="Comprueba que el servicio está en pie (útil para orquestadores).",
    response_description="Estado del servicio.",
    operation_id="healthCheck",
)
async def health() -> dict[str, str]:
    return {"status": "ok"}
