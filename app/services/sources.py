"""Validación de la fuente de un proyecto: una URL o un archivo del equipo.

Acá vale la distinción del brief: la frontera PROJECT_ROOT es una regla de
desarrollo, no del producto. La persona **sí** puede elegir un video que viva
en cualquier parte de su disco; lo que validamos es que sea un archivo real,
con una extensión que el core sepa leer, y en ruta absoluta (nada de rutas
relativas que dependan del cwd del servidor).
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

from ..core.errors import AppError

SOURCE_URL = "url"
SOURCE_FILE = "file"

MEDIA_EXTENSIONS = (
    ".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi",
    ".mp3", ".wav", ".m4a", ".aac", ".flac",
)

MAX_SOURCE_LENGTH = 2048


class InvalidSourceError(AppError):
    code = "invalid_source"
    status_code = 400


def classify_source(source: str) -> Tuple[str, str]:
    """Devolver `(source_type, source_normalizada)` o levantar `InvalidSourceError`."""
    source = (source or "").strip()
    if not source:
        raise InvalidSourceError("Pegá una URL o elegí un archivo de video.")
    if len(source) > MAX_SOURCE_LENGTH:
        raise InvalidSourceError("Esa dirección es demasiado larga.")

    parsed = urlparse(source)

    if parsed.scheme in ("http", "https"):
        if not parsed.netloc:
            raise InvalidSourceError("Esa URL no parece válida.")
        return SOURCE_URL, source

    if parsed.scheme and parsed.scheme != "file" and len(parsed.scheme) > 1:
        # `ftp://`, `javascript:`, etc. El core solo sabe de http(s) y archivos.
        raise InvalidSourceError(
            "Solo podemos trabajar con URLs http/https o con un archivo de tu equipo."
        )

    return SOURCE_FILE, _validate_file(source)


def _validate_file(source: str) -> str:
    path = Path(source).expanduser()
    if not path.is_absolute():
        raise InvalidSourceError(
            "Elegí el archivo con el selector: necesitamos la ruta completa.",
            detail="relative path rejected",
        )

    resolved = path.resolve()
    if not resolved.exists():
        raise InvalidSourceError("No encontramos ese archivo en tu equipo.")
    if not resolved.is_file():
        raise InvalidSourceError("Esa ruta no es un archivo de video.")
    if resolved.suffix.lower() not in MEDIA_EXTENSIONS:
        raise InvalidSourceError(
            "No reconocemos ese formato. Probá con {0}.".format(
                ", ".join(ext.lstrip(".") for ext in MEDIA_EXTENSIONS[:6])
            )
        )
    return str(resolved)
