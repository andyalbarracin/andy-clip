"""Persistencia de proyectos, highlights y clips."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.errors import AppError
from .db import Database

# Estados de un proyecto.
DRAFT = "draft"
PROCESSING = "processing"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

MESES = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)

MAX_NAME_LENGTH = 120


class ProjectNotFound(AppError):
    code = "project_not_found"
    status_code = 404


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def default_project_name(moment: Optional[datetime] = None) -> str:
    """«Video 17 ago 2026 - 13:30» — sin depender del locale del sistema."""
    moment = moment or datetime.now()
    return "Video {0} {1} {2} - {3:02d}:{4:02d}".format(
        moment.day, MESES[moment.month - 1], moment.year, moment.hour, moment.minute
    )


def clean_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise AppError("El nombre no puede quedar vacío.")
    if len(name) > MAX_NAME_LENGTH:
        raise AppError("El nombre no puede superar los {0} caracteres.".format(MAX_NAME_LENGTH))
    return name


def _loads(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class ProjectRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    # ── proyectos ────────────────────────────────────────────────────────────

    def create(
        self,
        source: str,
        source_type: str,
        settings: Dict[str, Any],
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        project_id = new_id()
        timestamp = now_iso()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects
                    (id, name, source, source_type, status, settings, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    clean_name(name) if name else default_project_name(),
                    source,
                    source_type,
                    DRAFT,
                    json.dumps(settings, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(project_id)

    def get(self, project_id: str) -> Dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise ProjectNotFound("No encontramos ese proyecto.")
        return self._row_to_project(row)

    def list(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC "
                "LIMIT ? OFFSET ?",
                (max(1, min(limit, 200)), max(0, offset)),
            ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def count(self) -> int:
        with self.db.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0])

    def rename(self, project_id: str, name: str) -> Dict[str, Any]:
        self.get(project_id)  # 404 si no existe
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
                (clean_name(name), now_iso(), project_id),
            )
        return self.get(project_id)

    def set_status(
        self,
        project_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE projects SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, error, now_iso(), project_id),
            )

    def update_settings(self, project_id: str, settings: Dict[str, Any]) -> None:
        """Las opciones con las que se generó el resultado que estás viendo."""
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE projects SET settings = ?, updated_at = ? WHERE id = ?",
                (json.dumps(settings, ensure_ascii=False), now_iso(), project_id),
            )

    def set_media_path(self, project_id: str, media_path: str) -> None:
        """Dónde quedó el video de origen ya descargado.

        Es lo que permite volver a generar los clips con otro encuadre sin
        descargar, transcribir ni analizar de nuevo.
        """
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE projects SET media_path = ?, updated_at = ? WHERE id = ?",
                (media_path, now_iso(), project_id),
            )

    def set_transcript(
        self, project_id: str, transcript: Dict[str, Any], duration: Optional[float] = None
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE projects SET transcript = ?, duration = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(transcript, ensure_ascii=False),
                    duration if duration is not None else transcript.get("duration"),
                    now_iso(),
                    project_id,
                ),
            )

    def delete(self, project_id: str) -> None:
        """Borra el proyecto del historial.

        No toca ningún archivo: ni el video original de la persona ni los clips
        que ya se generaron. Eso queda a cargo de quien use la app.
        """
        self.get(project_id)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # ── highlights ───────────────────────────────────────────────────────────

    def replace_highlights(
        self, project_id: str, highlights: List[Dict[str, Any]], selected_count: int
    ) -> List[Dict[str, Any]]:
        """Guardar todos los candidatos, marcando los que se van a recortar."""
        ordered = sorted(highlights, key=lambda h: int(h.get("score", 0)), reverse=True)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM highlights WHERE project_id = ?", (project_id,))
            for position, highlight in enumerate(ordered):
                conn.execute(
                    """
                    INSERT INTO highlights
                        (id, project_id, position, title, start_time, end_time, score,
                         hook_sentence, virality_reason, selected)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id(),
                        project_id,
                        position,
                        str(highlight.get("title") or "Sin título"),
                        float(highlight.get("start_time", 0.0)),
                        float(highlight.get("end_time", 0.0)),
                        int(highlight.get("score", 0)),
                        highlight.get("hook_sentence") or "",
                        highlight.get("virality_reason") or "",
                        1 if position < selected_count else 0,
                    ),
                )
        return self.highlights(project_id)

    def update_highlight(
        self, project_id: str, highlight_id: str, start_time: float, end_time: float
    ) -> Dict[str, Any]:
        """Mover los puntos de entrada y salida de un momento.

        Es lo que hace el recorte del editor: no se vuelve a analizar nada, solo
        cambia de dónde a dónde se corta.
        """
        if end_time <= start_time:
            raise AppError("El final tiene que ser posterior al comienzo.")
        if start_time < 0:
            raise AppError("El comienzo no puede ser negativo.")

        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE highlights SET start_time = ?, end_time = ? "
                "WHERE id = ? AND project_id = ?",
                (float(start_time), float(end_time), highlight_id, project_id),
            )
            if cursor.rowcount == 0:
                raise ProjectNotFound("No encontramos ese momento.")

        return next(
            h for h in self.highlights(project_id) if h["id"] == highlight_id
        )

    def set_highlight_selected(
        self, project_id: str, highlight_id: str, selected: bool
    ) -> None:
        """Incluir o sacar un momento de los que se van a generar."""
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE highlights SET selected = ? WHERE id = ? AND project_id = ?",
                (1 if selected else 0, highlight_id, project_id),
            )
            if cursor.rowcount == 0:
                raise ProjectNotFound("No encontramos ese momento.")

    def highlights(self, project_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM highlights WHERE project_id = ? ORDER BY position",
                (project_id,),
            ).fetchall()
        return [self._row_to_highlight(row) for row in rows]

    # ── clips ────────────────────────────────────────────────────────────────

    def add_clip(
        self,
        project_id: str,
        position: int,
        aspect_ratio: str,
        highlight_id: Optional[str] = None,
        path: Optional[str] = None,
        duration: Optional[float] = None,
        status: str = "done",
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        clip_id = new_id()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO clips
                    (id, project_id, highlight_id, position, path, aspect_ratio,
                     duration, status, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clip_id,
                    project_id,
                    highlight_id,
                    position,
                    path,
                    aspect_ratio,
                    duration,
                    status,
                    error,
                    now_iso(),
                ),
            )
        return self.clip(clip_id)

    def clip(self, clip_id: str) -> Dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
        if row is None:
            raise ProjectNotFound("No encontramos ese clip.")
        return dict(row)

    def clips(self, project_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM clips WHERE project_id = ? ORDER BY position",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_clips(self, project_id: str) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM clips WHERE project_id = ?", (project_id,))

    def recent_clips(self, limit: int = 6) -> List[Dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT clips.*, projects.name AS project_name
                FROM clips JOIN projects ON projects.id = clips.project_id
                WHERE clips.path IS NOT NULL
                ORDER BY clips.created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 50)),),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── mapeo ────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_project(row: Any) -> Dict[str, Any]:
        project = dict(row)
        project["settings"] = _loads(project.get("settings"), {})
        project["transcript"] = _loads(project.get("transcript"), None)
        return project

    @staticmethod
    def _row_to_highlight(row: Any) -> Dict[str, Any]:
        highlight = dict(row)
        highlight["selected"] = bool(highlight["selected"])
        highlight["duration"] = round(
            float(highlight["end_time"]) - float(highlight["start_time"]), 2
        )
        return highlight
