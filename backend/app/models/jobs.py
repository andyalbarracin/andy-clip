"""Persistencia de jobs de procesamiento."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from ..core.errors import AppError
from .db import Database
from .projects import new_id, now_iso

# Estados de un job.
PENDING = "pending"        # Pendiente
QUEUED = "queued"          # En cola
PROCESSING = "processing"  # Procesando
DONE = "done"              # Finalizado
FAILED = "failed"          # Fallido
CANCELLED = "cancelled"    # Cancelado

ACTIVE_STATUSES = (PENDING, QUEUED, PROCESSING)
FINAL_STATUSES = (DONE, FAILED, CANCELLED)

STATUS_LABELS: Dict[str, str] = {
    PENDING: "Pendiente",
    QUEUED: "En cola",
    PROCESSING: "Procesando",
    DONE: "Finalizado",
    FAILED: "Fallido",
    CANCELLED: "Cancelado",
}

# Etapas del pipeline, en orden. La UI las muestra tal cual.
STAGES: "OrderedDict[str, str]" = OrderedDict(
    [
        ("preparing", "Preparando fuente"),
        ("downloading", "Descargando"),
        ("transcribing", "Transcribiendo"),
        ("analyzing", "Analizando contenido"),
        ("finding_highlights", "Buscando mejores momentos"),
        ("selecting", "Seleccionando clips"),
        ("rendering", "Generando videos"),
        ("reframing", "Reencuadrando"),
        ("finished", "Finalizado"),
    ]
)


class JobNotFound(AppError):
    code = "job_not_found"
    status_code = 404


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def create(self, project_id: str) -> Dict[str, Any]:
        job_id = new_id()
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, project_id, status, stage, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, project_id, PENDING, None, now_iso()),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> Dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFound("No encontramos ese procesamiento.")
        return self._row_to_job(row)

    def latest_for_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def active(self) -> List[Dict[str, Any]]:
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status IN ({0}) ORDER BY created_at".format(
                    placeholders
                ),
                ACTIVE_STATUSES,
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def update(self, job_id: str, **fields: Any) -> Dict[str, Any]:
        allowed = {
            "status", "stage", "message", "progress", "error",
            "started_at", "completed_at", "cancel_requested",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return self.get(job_id)

        assignments = ", ".join("{0} = ?".format(key) for key in updates)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE jobs SET {0} WHERE id = ?".format(assignments),
                list(updates.values()) + [job_id],
            )
        return self.get(job_id)

    def request_cancel(self, job_id: str) -> Dict[str, Any]:
        self.get(job_id)
        with self.db.connect() as conn:
            conn.execute("UPDATE jobs SET cancel_requested = 1 WHERE id = ?", (job_id,))
        return self.get(job_id)

    def cancel_requested(self, job_id: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return bool(row and row[0])

    def reset_orphans(self) -> int:
        """Marcar como fallidos los jobs que quedaron colgados de una corrida previa.

        Si el backend se cerró mientras procesaba, en la base quedan jobs en
        `processing` que ya no tienen worker. Al arrancar los cerramos para que
        la UI no muestre un progreso eterno.
        """
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, error = ?, completed_at = ? "
                "WHERE status IN (?, ?, ?)",
                (
                    FAILED,
                    "El procesamiento se interrumpió porque se cerró la aplicación.",
                    now_iso(),
                    PENDING,
                    QUEUED,
                    PROCESSING,
                ),
            )
            return cursor.rowcount

    @staticmethod
    def _row_to_job(row: Any) -> Dict[str, Any]:
        job = dict(row)
        job["cancel_requested"] = bool(job.get("cancel_requested"))
        job["status_label"] = STATUS_LABELS.get(job.get("status", ""), job.get("status"))
        job["stage_label"] = STAGES.get(job.get("stage") or "", None)
        return job
