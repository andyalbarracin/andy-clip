"""Cola local de procesamiento: un job pesado por vez.

V1 no necesita Redis ni Celery. Un hilo worker con una `queue.Queue` alcanza
para un uso single-user, y deja la cancelación en algo que se puede razonar:
el runner recibe un `JobContext`, avisa en qué etapa está y chequea si le
pidieron cancelar.

El runner es un callable — así el manager no sabe nada del pipeline y se puede
testear sin video, sin FFmpeg y sin llamadas pagas.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Dict, List, Optional

from ..core.errors import AppError
from ..core.logging import get_logger
from ..models import jobs as job_states
from ..models import projects as project_states
from ..models.jobs import JobRepository
from ..models.projects import ProjectRepository, now_iso

logger = get_logger("andy_clip.jobs")


class JobCancelled(Exception):
    """La persona pidió cancelar; el runner corta donde esté."""


class JobBusy(AppError):
    code = "job_busy"
    status_code = 409


class JobContext:
    """Lo que el runner ve del job: dónde reportar y cuándo frenar."""

    def __init__(
        self,
        job_id: str,
        project_id: str,
        jobs: JobRepository,
        cancel_event: threading.Event,
    ) -> None:
        self.job_id = job_id
        self.project_id = project_id
        self._jobs = jobs
        self._cancel_event = cancel_event
        self._cancel_hooks: List[Callable[[], None]] = []

    # ── progreso ─────────────────────────────────────────────────────────────

    def stage(
        self,
        stage: str,
        message: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Avanzar de etapa. `progress` solo si es un porcentaje real."""
        self.raise_if_cancelled()
        self._jobs.update(
            self.job_id,
            stage=stage,
            message=message or job_states.STAGES.get(stage),
            progress=progress,
        )

    # ── cancelación ──────────────────────────────────────────────────────────

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise JobCancelled()

    def on_cancel(self, hook: Callable[[], None]) -> None:
        """Registrar cómo frenar un trabajo en curso (por ejemplo, matar un subproceso)."""
        self._cancel_hooks.append(hook)
        if self.cancelled:
            self._run_hooks()

    def _run_hooks(self) -> None:
        for hook in self._cancel_hooks:
            try:
                hook()
            except Exception:  # pragma: no cover - un hook roto no debe tumbar el worker
                logger.exception("cancel hook failed for job %s", self.job_id)


Runner = Callable[[JobContext], None]


class JobManager:
    """Un worker, una cola, un job pesado a la vez."""

    def __init__(self, jobs: JobRepository, projects: ProjectRepository) -> None:
        self.jobs = jobs
        self.projects = projects
        self._queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._cancel_events: Dict[str, threading.Event] = {}
        self._current: Optional[JobContext] = None

    # ── ciclo de vida ────────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._work, name="andy-clip-jobs", daemon=True
            )
            self._worker.start()

    def shutdown(self, timeout: float = 5.0) -> None:
        self._queue.put(None)
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=timeout)
        self._worker = None

    # ── API ──────────────────────────────────────────────────────────────────

    def submit(self, project_id: str, runner: Runner) -> Dict[str, Any]:
        """Encolar un procesamiento. Rechaza si ya hay uno en curso."""
        active = [j for j in self.jobs.active()]
        if active:
            raise JobBusy(
                "Ya hay un video procesándose. Esperá a que termine o cancelalo.",
                detail="active job {0}".format(active[0]["id"]),
            )

        job = self.jobs.create(project_id)
        self._cancel_events[job["id"]] = threading.Event()
        self.jobs.update(job["id"], status=job_states.QUEUED)
        self._queue.put({"job_id": job["id"], "project_id": project_id, "runner": runner})
        self.start()
        return self.jobs.get(job["id"])

    def cancel(self, job_id: str) -> Dict[str, Any]:
        job = self.jobs.get(job_id)
        if job["status"] in job_states.FINAL_STATUSES:
            return job

        self.jobs.request_cancel(job_id)
        event = self._cancel_events.get(job_id)
        if event:
            event.set()

        current = self._current
        if current and current.job_id == job_id:
            # En curso: disparamos los hooks (matar subproceso) y el runner corta.
            current._run_hooks()
        else:
            # Todavía en cola: lo cerramos acá mismo.
            self._finish(job_id, job["project_id"], job_states.CANCELLED)
        return self.jobs.get(job_id)

    @property
    def busy(self) -> bool:
        return self._current is not None

    # ── worker ───────────────────────────────────────────────────────────────

    def _work(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            try:
                self._run_one(item)
            finally:
                self._queue.task_done()

    def _run_one(self, item: Dict[str, Any]) -> None:
        job_id = item["job_id"]
        project_id = item["project_id"]
        event = self._cancel_events.get(job_id) or threading.Event()

        job = self.jobs.get(job_id)
        if job["status"] in job_states.FINAL_STATUSES or event.is_set():
            self._finish(job_id, project_id, job_states.CANCELLED)
            return

        context = JobContext(job_id, project_id, self.jobs, event)
        self._current = context
        # El estado del job se escribe último, siempre: la UI lo usa como
        # señal de "ya podés leer el proyecto", así que nunca debe adelantarse.
        self.projects.set_status(project_id, project_states.PROCESSING)
        self.jobs.update(
            job_id,
            status=job_states.PROCESSING,
            started_at=now_iso(),
            stage="preparing",
            message=job_states.STAGES["preparing"],
        )

        try:
            item["runner"](context)
        except JobCancelled:
            self._finish(job_id, project_id, job_states.CANCELLED)
        except AppError as exc:
            logger.warning("job %s failed: %s", job_id, exc.detail or exc.message)
            self._finish(job_id, project_id, job_states.FAILED, error=exc.message)
        except Exception as exc:  # noqa: BLE001 - el worker nunca debe morir
            logger.exception("job %s crashed", job_id)
            self._finish(
                job_id,
                project_id,
                job_states.FAILED,
                error="El procesamiento se interrumpió por un error inesperado.",
                detail="{0}: {1}".format(type(exc).__name__, exc),
            )
        else:
            if event.is_set():
                self._finish(job_id, project_id, job_states.CANCELLED)
            else:
                self._finish(job_id, project_id, job_states.DONE)
        finally:
            self._current = None
            self._cancel_events.pop(job_id, None)

    def _finish(
        self,
        job_id: str,
        project_id: str,
        status: str,
        error: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        project_status = {
            job_states.DONE: project_states.DONE,
            job_states.FAILED: project_states.FAILED,
            job_states.CANCELLED: project_states.CANCELLED,
        }.get(status, project_states.DRAFT)
        self.projects.set_status(project_id, project_status, error=error)

        # Después del proyecto: cuando el job dice "terminado", el proyecto ya
        # está actualizado y no hay ventana para leer estados contradictorios.
        stage = "finished" if status == job_states.DONE else None
        self.jobs.update(
            job_id,
            status=status,
            error=error,
            completed_at=now_iso(),
            **({"stage": stage, "message": job_states.STAGES[stage]} if stage else {})
        )
        if detail:
            logger.info("job %s finished as %s — %s", job_id, status, detail)
