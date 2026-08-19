"""Backend local de Andy Clip.

Escucha en 127.0.0.1: es una aplicación de escritorio servida por HTTP, no un
servicio expuesto a la red. Arranca siempre, con o sin API keys: la falta de
credenciales bloquea una acción puntual, nunca la apertura de la app.

    .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8756
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.deps import get_database
from .api.routes import health, jobs as jobs_routes, projects as projects_routes
from .api.routes import settings as settings_routes
from .api.routes import uploads as uploads_routes
from .core.errors import AppError
from .models.jobs import JobRepository
from .core.logging import LOG_LEVEL, get_logger, setup_logging
from .core.paths import PROJECT_ROOT, ensure_dirs
from .core.settings import APP_NAME, APP_VERSION

logger = get_logger("andy_clip.api")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8756

# La interfaz compilada. Con esto Andy Clip es un solo proceso.
WEB_DIST = PROJECT_ROOT / "web" / "dist"

# Orígenes del frontend en desarrollo (Vite). Sin comodines.
DEV_ORIGINS: List[str] = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:{0}".format(DEFAULT_PORT),
    "http://localhost:{0}".format(DEFAULT_PORT),
]


def _error_response(
    status_code: int, code: str, message: str, action: Any = None, **extra: Any
) -> JSONResponse:
    payload: Dict[str, Any] = {"code": code, "message": message}
    if action:
        payload["action"] = action
    payload.update(extra)
    return JSONResponse(status_code=status_code, content={"error": payload})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database = get_database()
    database.initialize()
    # Si el backend se cerró en medio de un procesamiento, esos jobs quedaron
    # sin worker: los cerramos para no mostrar un progreso eterno.
    orphans = JobRepository(database).reset_orphans()
    if orphans:
        logger.info("closed %s interrupted job(s) from a previous run", orphans)
    yield


def create_app() -> FastAPI:
    setup_logging(LOG_LEVEL)
    ensure_dirs()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Backend local de {0}.".format(APP_NAME),
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        # El detalle técnico va al log; a la pantalla va solo `message`.
        logger.warning("%s on %s — %s", exc.code, request.url.path, exc.detail or exc.message)
        return _error_response(exc.status_code, exc.code, exc.message, exc.action)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Reportamos dónde falló, nunca con qué valor: el input puede ser una API key.
        fields = [
            {"field": ".".join(str(part) for part in error.get("loc", [])[1:]),
             "message": error.get("msg", "")}
            for error in exc.errors()
        ]
        return _error_response(
            422, "invalid_request", "Revisá los datos que enviaste.", fields=fields
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s", request.url.path)
        return _error_response(
            500,
            "internal_error",
            "Algo se rompió de nuestro lado. Revisá los logs del servidor para el detalle.",
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(settings_routes.router, prefix="/api")
    app.include_router(projects_routes.router, prefix="/api")
    app.include_router(jobs_routes.router, prefix="/api")
    app.include_router(uploads_routes.router, prefix="/api")

    mount_web(app)

    return app


def mount_web(app: FastAPI) -> None:
    """Servir la interfaz ya compilada desde el mismo servidor.

    Con esto Andy Clip es un solo proceso y una sola dirección. Si `web/dist`
    todavía no existe (nadie compiló el frontend), la API sigue funcionando y
    la raíz explica qué falta en vez de tirar un 404 mudo.
    """
    index = WEB_DIST / "index.html"

    if index.exists():
        assets = WEB_DIST / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_web(full_path: str):
        # Las rutas de API ya se resolvieron más arriba: si algo cae acá con
        # prefijo /api, es que no existe.
        if full_path.startswith("api/"):
            return _error_response(404, "not_found", "Esa dirección no existe.")

        if index.exists():
            return FileResponse(str(index))

        return _error_response(
            503,
            "web_not_built",
            "La interfaz todavía no está compilada. Ejecutá ./start.sh, o "
            "'npm install && npm run build' dentro de web/.",
        )


app = create_app()


def main() -> None:  # pragma: no cover - entry point
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.environ.get("ANDY_CLIP_HOST", DEFAULT_HOST),
        port=int(os.environ.get("ANDY_CLIP_PORT", DEFAULT_PORT)),
        log_level=LOG_LEVEL,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
