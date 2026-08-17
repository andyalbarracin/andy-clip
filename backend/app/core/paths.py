"""Filesystem layout for Andy Clip.

Everything the app writes lives under PROJECT_ROOT: clips, temporales, la base
SQLite y el archivo privado de secrets. `ensure_within` es la única puerta que
impide que un path elegido por el usuario se escape de esos directorios.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from .errors import PathValidationError

# backend/app/core/paths.py → backend/app/core → backend/app → backend → PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / "temp"
LOCAL_DIR = PROJECT_ROOT / ".local"

PathLike = Union[str, "os.PathLike[str]"]


def ensure_dirs() -> None:
    """Create the runtime directories. `.local/` gets restrictive permissions."""
    for directory in (DATA_DIR, OUTPUT_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        LOCAL_DIR.chmod(0o700)
    except OSError:
        # Some filesystems (network shares, Windows) don't support this. Not fatal.
        pass


def ensure_within(base: PathLike, candidate: PathLike) -> Path:
    """Resolve `candidate` and assert it stays inside `base`.

    Symlinks are resolved first, so a symlink pointing outside `base` is
    rejected too.
    """
    base_resolved = Path(base).resolve()
    candidate_path = Path(candidate).expanduser()
    if not candidate_path.is_absolute():
        candidate_path = base_resolved / candidate_path
    candidate_resolved = candidate_path.resolve()

    if candidate_resolved != base_resolved and base_resolved not in candidate_resolved.parents:
        raise PathValidationError(
            "Esa ruta está fuera de la carpeta del proyecto.",
            detail="{0} escapes {1}".format(candidate_resolved, base_resolved),
        )
    return candidate_resolved
