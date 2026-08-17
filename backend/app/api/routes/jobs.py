"""Estado y cancelación de los procesamientos."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...models.jobs import STAGES, JobRepository
from ...services.job_manager import JobManager
from ..deps import get_job_manager, get_jobs

router = APIRouter(prefix="/jobs", tags=["procesamiento"])


@router.get("/stages")
def list_stages() -> Dict[str, Any]:
    """Las etapas del pipeline, en orden, para dibujar el progreso."""
    return {"stages": [{"id": key, "label": label} for key, label in STAGES.items()]}


@router.get("/active")
def active_jobs(jobs: JobRepository = Depends(get_jobs)) -> Dict[str, Any]:
    active = jobs.active()
    return {"jobs": active, "busy": bool(active)}


@router.get("/{job_id}")
def read_job(job_id: str, jobs: JobRepository = Depends(get_jobs)) -> Dict[str, Any]:
    return {"job": jobs.get(job_id)}


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    manager: JobManager = Depends(get_job_manager),
) -> Dict[str, Any]:
    """Pedir la cancelación.

    Marca el job, corta los procesos propios y limpia lo que haya quedado a
    medio hacer. Nunca toca el video original.
    """
    return {"job": manager.cancel(job_id)}
