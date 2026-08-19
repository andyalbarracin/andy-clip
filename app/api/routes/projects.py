"""Proyectos: alta, listado, detalle, renombrar y eliminar del historial."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from ...core.errors import AppError
from ...core.paths import PROJECT_ROOT, ensure_within
from ...core.secrets import SecretsService
from ...core.settings import SettingsStore, processing_options_for, validate_processing_options
from ...models.jobs import JobRepository
from ...models.projects import ProjectNotFound, ProjectRepository
from ...schemas.projects import HighlightEdit, ProjectCreate, ProjectRename, RerenderBody
from ...services import diagnostics
from ...services.job_manager import JobManager
from ...services.pipeline import build_render_runner, build_runner
from ...services.sources import classify_source
from ..deps import (
    get_job_manager,
    get_jobs,
    get_projects,
    get_secrets,
    get_settings_store,
)

router = APIRouter(tags=["proyectos"])


def _detail(
    project_id: str, projects: ProjectRepository, jobs: JobRepository
) -> Dict[str, Any]:
    project = projects.get(project_id)
    return {
        "project": project,
        "highlights": projects.highlights(project_id),
        "clips": projects.clips(project_id),
        "job": jobs.latest_for_project(project_id),
    }


@router.get("/home")
def home(
    projects: ProjectRepository = Depends(get_projects),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    """Lo que necesita el Inicio en una sola llamada."""
    return {
        "recent_projects": projects.list(limit=5),
        "recent_clips": projects.recent_clips(limit=6),
        "total_projects": projects.count(),
        "system": [c.as_dict() for c in diagnostics.home_components(secrets)],
        "local_mode": diagnostics.local_mode_is_ready(secrets),
    }


@router.post("/projects", status_code=201)
def create_project(
    body: ProjectCreate,
    projects: ProjectRepository = Depends(get_projects),
    jobs: JobRepository = Depends(get_jobs),
    store: SettingsStore = Depends(get_settings_store),
) -> Dict[str, Any]:
    source_type, source = classify_source(body.source)
    options = processing_options_for(
        store.resolve(),
        body.options.model_dump(exclude_unset=True) if body.options else None,
    )
    project = projects.create(
        source=source,
        source_type=source_type,
        settings=options.model_dump(),
        name=body.name,
    )
    return _detail(project["id"], projects, jobs)


@router.get("/projects")
def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    projects: ProjectRepository = Depends(get_projects),
) -> Dict[str, Any]:
    return {
        "projects": projects.list(limit=limit, offset=offset),
        "total": projects.count(),
    }


@router.get("/projects/{project_id}")
def read_project(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
    jobs: JobRepository = Depends(get_jobs),
) -> Dict[str, Any]:
    return _detail(project_id, projects, jobs)


@router.patch("/projects/{project_id}")
def rename_project(
    project_id: str,
    body: ProjectRename,
    projects: ProjectRepository = Depends(get_projects),
    jobs: JobRepository = Depends(get_jobs),
) -> Dict[str, Any]:
    projects.rename(project_id, body.name)
    return _detail(project_id, projects, jobs)


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
) -> Dict[str, Any]:
    """Elimina el proyecto del historial.

    No borra el video original ni los clips ya generados: quedan en disco.
    """
    projects.delete(project_id)
    return {"deleted": project_id, "files_kept": True}


@router.post("/projects/{project_id}/process", status_code=202)
def process_project(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
    jobs: JobRepository = Depends(get_jobs),
    secrets: SecretsService = Depends(get_secrets),
    store: SettingsStore = Depends(get_settings_store),
    manager: JobManager = Depends(get_job_manager),
) -> Dict[str, Any]:
    """Poner el proyecto en la cola.

    Todo lo que puede fallar por configuración —falta la API key, falta
    FFmpeg— se comprueba acá, antes de encolar: es mejor enterarse ahora que
    dentro de un trabajo que se va a caer en la mitad.
    """
    project = projects.get(project_id)
    runner = build_runner(project, store.resolve(), secrets, projects)
    job = manager.submit(project_id, runner)
    return {"job": job}


@router.post("/projects/{project_id}/rerender", status_code=202)
def rerender_project(
    project_id: str,
    body: RerenderBody,
    projects: ProjectRepository = Depends(get_projects),
    manager: JobManager = Depends(get_job_manager),
) -> Dict[str, Any]:
    """Volver a generar los clips con otros ajustes.

    No descarga, no transcribe y no llama a la IA: reusa el video y los momentos
    que ya están guardados. Por eso el editor puede probar encuadres sin costo.
    """
    project = projects.get(project_id)

    cambios = body.model_dump(exclude_unset=True, exclude_none=True)
    options = validate_processing_options({**project["settings"], **cambios})

    projects.update_settings(project_id, options.model_dump())
    runner = build_render_runner({**project, "settings": options.model_dump()}, options, projects)
    job = manager.submit(project_id, runner)
    return {"job": job}


@router.get("/projects/{project_id}/transcript")
def read_transcript(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
) -> Dict[str, Any]:
    project = projects.get(project_id)
    transcript = project.get("transcript") or {"duration": 0, "segments": []}
    return {
        "duration": transcript.get("duration", 0),
        "segments": transcript.get("segments", []),
    }


@router.get("/projects/{project_id}/media")
def read_project_media(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
) -> FileResponse:
    """El video original, para poder previsualizar el recorte en la interfaz.

    Sin esto el editor tendría que adivinar cómo va a quedar el corte. El
    archivo puede estar fuera del proyecto —la persona lo eligió de su disco—
    así que lo único que validamos es que sea el que este proyecto registró.
    """
    project = projects.get(project_id)
    media_path = project.get("media_path")

    if not media_path or not Path(media_path).is_file():
        raise AppError(
            "No tenemos el video original de este proyecto guardado.",
            detail="missing media for project {0}".format(project_id),
        )

    return FileResponse(media_path, media_type="video/mp4")


@router.patch("/projects/{project_id}/highlights/{highlight_id}")
def edit_highlight(
    project_id: str,
    highlight_id: str,
    body: HighlightEdit,
    projects: ProjectRepository = Depends(get_projects),
) -> Dict[str, Any]:
    """Ajustar el recorte de un momento antes de volver a generarlo."""
    actual = next(
        (h for h in projects.highlights(project_id) if h["id"] == highlight_id), None
    )
    if actual is None:
        raise ProjectNotFound("No encontramos ese momento.")

    if body.selected is not None:
        projects.set_highlight_selected(project_id, highlight_id, body.selected)

    if body.start_time is not None or body.end_time is not None:
        projects.update_highlight(
            project_id,
            highlight_id,
            body.start_time if body.start_time is not None else actual["start_time"],
            body.end_time if body.end_time is not None else actual["end_time"],
        )

    return {"highlights": projects.highlights(project_id)}


@router.get("/projects/{project_id}/highlights")
def read_highlights(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
) -> Dict[str, Any]:
    projects.get(project_id)
    return {"highlights": projects.highlights(project_id)}


@router.get("/projects/{project_id}/clips")
def read_clips(
    project_id: str,
    projects: ProjectRepository = Depends(get_projects),
) -> Dict[str, Any]:
    projects.get(project_id)
    return {"clips": projects.clips(project_id)}


@router.get("/clips/{clip_id}/file")
def read_clip_file(
    clip_id: str,
    download: bool = Query(default=False),
    projects: ProjectRepository = Depends(get_projects),
) -> FileResponse:
    """Servir el mp4 para el preview y la descarga.

    El path sale de la base (lo escribimos nosotros), pero igual lo validamos
    contra PROJECT_ROOT antes de abrirlo.
    """
    clip = projects.clip(clip_id)
    if not clip.get("path"):
        raise ProjectNotFound("Ese clip todavía no tiene archivo.")

    path = ensure_within(PROJECT_ROOT, clip["path"])
    if not Path(path).is_file():
        raise AppError(
            "No encontramos el archivo del clip. Puede que lo hayas movido o borrado.",
            detail="missing clip file: {0}".format(path),
        )

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=Path(path).name if download else None,
    )
