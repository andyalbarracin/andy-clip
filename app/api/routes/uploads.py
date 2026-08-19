"""Subir un video del equipo.

El navegador no le puede dar al backend la ruta real de un archivo —lo prohíbe
por seguridad—, así que para elegir un video con el selector del sistema hay
que subirlo. Como el servidor corre en la misma máquina, "subir" es copiar de
una carpeta a otra: no sale nada a internet.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, UploadFile

from ...core.errors import AppError
from ...core.paths import DATA_DIR
from ...services.sources import MEDIA_EXTENSIONS

router = APIRouter(tags=["fuentes"])

UPLOADS_DIR = DATA_DIR / "uploads"

# Un video largo puede pesar mucho; el límite existe para cortar un archivo
# desbocado, no para poner trabas.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024 * 1024  # 8 GB
CHUNK = 1024 * 1024


class UploadTooLarge(AppError):
    code = "upload_too_large"
    status_code = 413


@router.post("/uploads", status_code=201)
async def upload_video(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Guardar el archivo y devolver la ruta con la que crear un proyecto."""
    original = Path(file.filename or "video")
    extension = original.suffix.lower()

    if extension not in MEDIA_EXTENSIONS:
        raise AppError(
            "No reconocemos ese formato. Probá con {0}.".format(
                ", ".join(ext.lstrip(".") for ext in MEDIA_EXTENSIONS[:6])
            ),
            detail="rejected upload extension: {0!r}".format(extension),
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    # El nombre lo ponemos nosotros: el que trae el archivo es texto del usuario
    # y no tiene por qué ser un nombre de archivo válido ni seguro.
    destination = UPLOADS_DIR / "{0}{1}".format(uuid.uuid4().hex, extension)

    written = 0
    try:
        with destination.open("wb") as handle:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise UploadTooLarge("Ese archivo es demasiado grande para procesarlo acá.")
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if written == 0:
        destination.unlink(missing_ok=True)
        raise AppError("El archivo llegó vacío.")

    return {
        "path": str(destination),
        "name": original.name,
        "size": written,
    }


def free_space_hint() -> str:  # pragma: no cover - informativo
    usage = shutil.disk_usage(str(DATA_DIR))
    return "{0:.1f} GB libres".format(usage.free / 1e9)
