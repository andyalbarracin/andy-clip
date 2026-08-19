"""SQLite con la librería estándar.

Andy Clip es local y single-user: una base SQLite en `data/` alcanza y evita
sumar un ORM. Cada operación abre y cierra su propia conexión, así que los
repositorios se pueden usar desde el worker de jobs sin compartir conexiones
entre hilos (sqlite3 no lo permite).

La base guarda **metadata**: proyectos, jobs, highlights y clips. Nunca guarda
API keys — esas viven en `.local/secrets.json`.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from ..core.paths import DATA_DIR

SCHEMA_VERSION = 2

DEFAULT_DB_FILENAME = "andy-clip.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    source        TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    status        TEXT NOT NULL,
    settings      TEXT NOT NULL DEFAULT '{}',
    transcript    TEXT,
    duration      REAL,
    media_path    TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status           TEXT NOT NULL,
    stage            TEXT,
    message          TEXT,
    progress         REAL,
    error            TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    completed_at     TEXT
);

CREATE TABLE IF NOT EXISTS highlights (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    position        INTEGER NOT NULL,
    title           TEXT NOT NULL,
    start_time      REAL NOT NULL,
    end_time        REAL NOT NULL,
    score           INTEGER NOT NULL,
    hook_sentence   TEXT,
    virality_reason TEXT,
    selected        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS clips (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    highlight_id TEXT REFERENCES highlights(id) ON DELETE SET NULL,
    position     INTEGER NOT NULL,
    path         TEXT,
    aspect_ratio TEXT NOT NULL,
    duration     REAL,
    status       TEXT NOT NULL,
    error        TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_highlights_project ON highlights(project_id);
CREATE INDEX IF NOT EXISTS idx_clips_project ON clips(project_id);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
"""


class Database:
    """Dueña del archivo SQLite y del esquema."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else (DATA_DIR / DEFAULT_DB_FILENAME)
        self._initialized = False

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._raw_connection() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
            conn.execute("PRAGMA user_version = {0}".format(SCHEMA_VERSION))
            conn.commit()
        self._initialized = True

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Poner al día una base creada por una versión anterior.

        `CREATE TABLE IF NOT EXISTS` no agrega columnas nuevas a una tabla que
        ya existe, así que las sumamos a mano. Son pocas y el proyecto es de un
        solo usuario: no hace falta un sistema de migraciones.
        """
        columnas = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
        if "media_path" not in columnas:
            conn.execute("ALTER TABLE projects ADD COLUMN media_path TEXT")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self._initialized:
            self.initialize()
        with self._raw_connection() as conn:
            yield conn
            conn.commit()

    @contextmanager
    def _raw_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

    @property
    def schema_version(self) -> int:
        with self._raw_connection() as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])
