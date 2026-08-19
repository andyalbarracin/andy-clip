"""Lanza el procesamiento y traduce lo que informa a estado de la aplicación.

Este módulo es el puente entre la cola de trabajos y el proceso hijo que hace
el trabajo pesado: arma el entorno, lo ejecuta, lee sus eventos y los va
guardando. Nunca usa `shell=True`: los argumentos van en una lista.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..core.errors import AppError, DependencyMissingError
from ..core.logging import get_logger
from ..core.paths import DATA_DIR, OUTPUT_DIR, ensure_within
from ..core.secrets import ENV_VARS, SecretsService
from ..core.settings import (
    PROVIDERS,
    AppSettings,
    ProcessingOptions,
    validate_processing_options,
)
from ..models.projects import ProjectRepository
from .diagnostics import AVAILABLE, ffmpeg_status
from .job_manager import JobContext

logger = get_logger("andy_clip.pipeline")

WORKER_MODULE = "app.services.pipeline_worker"

# Dónde se guardan los modelos de transcripción que faster-whisper descarga.
MODELS_DIR = DATA_DIR / "models"


def project_output_dir(project_id: str) -> Path:
    """Una carpeta por proyecto, para que dos proyectos no se pisen los clips."""
    return ensure_within(OUTPUT_DIR, OUTPUT_DIR / project_id)


def _child_env(settings: AppSettings, secrets: SecretsService, options: ProcessingOptions) -> Dict[str, str]:
    """El entorno del proceso hijo, con la configuración ya resuelta.

    El motor lee estas variables al importarse, así que acá es donde la
    configuración de la aplicación se vuelve efectiva.
    """
    env = dict(os.environ)
    env.update(
        {
            # Los modelos de transcripción viven dentro del proyecto, no en la
            # caché global del sistema: así borrar la carpeta de Andy Clip se
            # lleva todo lo que ocupaba, sin dejar gigas huérfanos en ~/.cache.
            "HF_HUB_CACHE": str(MODELS_DIR),
            "LLM_PROVIDER": settings.ai.provider,
            "OPENAI_MODEL": settings.ai.openai_model,
            "GEMINI_MODEL": settings.ai.gemini_model,
            "LOCAL_WHISPER_MODEL": settings.transcription.whisper_model,
            "LOCAL_WHISPER_DEVICE": settings.transcription.device,
            "LOCAL_WHISPER_VAD_FILTER": "true" if settings.transcription.vad_filter else "false",
            "PYTHONUNBUFFERED": "1",
        }
    )

    env["GROQ_MODEL"] = settings.ai.groq_model

    # El proveedor elegido primero; detrás, los otros que tengan credencial.
    # Si el principal se queda sin saldo en la mitad del análisis, el motor
    # sigue con el siguiente en vez de perder todo el trabajo hecho.
    elegido = settings.ai.provider
    secrets.require(elegido)  # sin credencial no arrancamos

    orden = [elegido] + [p for p in PROVIDERS if p != elegido and secrets.has(p)]
    env["ANDY_CLIP_PROVIDER_ORDER"] = ",".join(orden)

    for provider in orden:
        env[ENV_VARS[provider]] = secrets.require(provider)

    if options.language:
        env["LOCAL_WHISPER_LANGUAGE"] = options.language

    return env


def build_runner(
    project: Dict[str, Any],
    settings: AppSettings,
    secrets: SecretsService,
    projects: ProjectRepository,
) -> Callable[[JobContext], None]:
    """Devolver el runner que la cola va a ejecutar para este proyecto."""
    options = validate_processing_options(project["settings"])

    if options.mode != "local":
        raise AppError(
            "Por ahora solo podemos procesar en modo local desde la aplicación.",
            detail="mode={0} not supported by the UI pipeline".format(options.mode),
            action="settings",
        )

    if ffmpeg_status().status != AVAILABLE:
        raise DependencyMissingError(
            "FFmpeg no está disponible en este equipo. Es necesario para generar "
            "clips localmente.",
            detail="ffmpeg missing",
        )

    # Se resuelve antes de encolar: si falta la API key, conviene enterarse
    # ahora y no dentro de un trabajo que va a fallar en la mitad.
    env = _child_env(settings, secrets, options)
    out_dir = project_output_dir(project["id"])

    def runner(ctx: JobContext) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        projects.clear_clips(project["id"])

        command = [
            sys.executable,
            "-u",
            "-m",
            WORKER_MODULE,
            "--source", project["source"],
            "--out-dir", str(out_dir),
            "--num-clips", str(options.num_clips),
            "--aspect-ratio", options.aspect_ratio,
            "--resolution", options.resolution,
            "--language", options.language or "",
            "--framing", options.framing,
            "--background", options.background,
            "--background-color", options.background_color,
        ]

        _run_worker(command, env, ctx, project["id"], projects)

    return runner


def build_render_runner(
    project: Dict[str, Any],
    options: ProcessingOptions,
    projects: ProjectRepository,
) -> Callable[[JobContext], None]:
    """Volver a generar los clips con otro encuadre, sin rehacer el análisis.

    Es lo que hace el editor: el video ya está bajado y los momentos ya están
    elegidos, así que esto cuesta segundos y no gasta una sola llamada a la IA.
    """
    media_path = project.get("media_path")
    if not media_path or not Path(media_path).is_file():
        raise AppError(
            "No tenemos el video original de este proyecto guardado, así que no "
            "podemos volver a generar los clips. Procesalo de nuevo desde cero.",
            detail="missing media_path for project {0}".format(project["id"]),
        )

    if ffmpeg_status().status != AVAILABLE:
        raise DependencyMissingError(
            "FFmpeg no está disponible en este equipo. Es necesario para generar "
            "clips localmente.",
            detail="ffmpeg missing",
        )

    chosen = [h for h in projects.highlights(project["id"]) if h["selected"]]
    if not chosen:
        raise AppError(
            "Este proyecto todavía no tiene momentos elegidos para generar."
        )

    out_dir = project_output_dir(project["id"])

    def runner(ctx: JobContext) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        projects.clear_clips(project["id"])

        clips_json = out_dir / "momentos.json"
        clips_json.write_text(
            json.dumps(
                [
                    {"start_time": h["start_time"], "end_time": h["end_time"]}
                    for h in chosen
                ]
            ),
            encoding="utf-8",
        )

        command = [
            sys.executable, "-u", "-m", WORKER_MODULE,
            "--render-only",
            "--source-path", str(media_path),
            "--clips-json", str(clips_json),
            "--out-dir", str(out_dir),
            "--aspect-ratio", options.aspect_ratio,
            "--resolution", options.resolution,
            "--framing", options.framing,
            "--background", options.background,
            "--background-color", options.background_color,
        ]

        _run_worker(command, dict(os.environ), ctx, project["id"], projects)

    return runner


def _run_worker(
    command: List[str],
    env: Dict[str, str],
    ctx: JobContext,
    project_id: str,
    projects: ProjectRepository,
) -> None:
    """Ejecutar el proceso hijo y traducir sus eventos."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        cwd=str(OUTPUT_DIR.parent),
    )

    ctx.on_cancel(lambda: _terminate(process))

    failure: Optional[str] = None
    try:
        for line in process.stdout or []:
            message = _handle_event(line, ctx, project_id, projects)
            if message:
                failure = message
    finally:
        stderr = (process.stderr.read() if process.stderr else "") or ""
        process.wait()

    if ctx.cancelled:
        ctx.raise_if_cancelled()

    if failure:
        raise AppError(failure, detail=stderr.strip()[-2000:] or None)

    if process.returncode != 0:
        logger.warning("worker exited with %s: %s", process.returncode, stderr.strip()[-2000:])
        raise AppError(
            "El procesamiento se interrumpió antes de terminar.",
            detail="worker exit {0}".format(process.returncode),
        )

    clips = projects.clips(project_id)
    if not any(clip["path"] for clip in clips):
        raise AppError("No pudimos generar ningún clip de este video.")


def _handle_event(
    line: str, ctx: JobContext, project_id: str, projects: ProjectRepository
) -> Optional[str]:
    """Procesar un evento del worker. Devuelve un mensaje si el evento es un error."""
    line = line.strip()
    if not line:
        return None

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # El motor imprime sus propios avisos; no son eventos, van al log.
        logger.debug("worker: %s", line[:500])
        return None

    kind = event.get("event")

    if kind == "stage":
        ctx.stage(
            event["stage"],
            message=event.get("message"),
            progress=event.get("progress"),
        )
    elif kind == "source":
        projects.set_media_path(project_id, event["path"])
    elif kind == "transcript":
        transcript = event["transcript"]
        projects.set_transcript(project_id, transcript, duration=transcript.get("duration"))
    elif kind == "highlights":
        projects.replace_highlights(
            project_id, event["highlights"], selected_count=int(event.get("selected", 0))
        )
    elif kind == "clip":
        _save_clip(event, project_id, projects)
    elif kind == "error":
        logger.warning("worker error: %s", event.get("detail") or event.get("message"))
        return str(event.get("message", "No pudimos completar el procesamiento."))

    return None


def _save_clip(event: Dict[str, Any], project_id: str, projects: ProjectRepository) -> None:
    highlights: List[Dict[str, Any]] = projects.highlights(project_id)
    match = next(
        (
            h
            for h in highlights
            if abs(float(h["start_time"]) - float(event.get("start_time", -1))) < 0.01
        ),
        None,
    )
    project = projects.get(project_id)

    projects.add_clip(
        project_id,
        position=int(event.get("position", 0)),
        aspect_ratio=str(project["settings"].get("aspect_ratio", "9:16")),
        highlight_id=match["id"] if match else None,
        path=event.get("path"),
        duration=event.get("duration"),
        status=str(event.get("status", "done")),
        error=event.get("error"),
    )


def _terminate(process: "subprocess.Popen[str]") -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - proceso obstinado
        process.kill()
