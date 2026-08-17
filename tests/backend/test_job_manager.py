"""Cola de procesamiento: un job por vez, progreso y cancelación real."""
from __future__ import annotations

import threading

import pytest

from backend.app.core.errors import AppError
from backend.app.models import jobs as job_states
from backend.app.models import projects as project_states
from backend.app.services.job_manager import JobBusy

TIMEOUT = 5.0

OPTIONS = {"mode": "local", "num_clips": 3, "aspect_ratio": "9:16", "resolution": "720"}


@pytest.fixture
def project(projects_repo):
    return projects_repo.create(
        source="https://www.youtube.com/watch?v=abc",
        source_type="url",
        settings=OPTIONS,
    )


def _wait_for(jobs_repo, job_id, statuses, timeout=TIMEOUT):
    deadline = threading.Event()
    for _ in range(int(timeout / 0.02)):
        job = jobs_repo.get(job_id)
        if job["status"] in statuses:
            return job
        deadline.wait(0.02)
    raise AssertionError(
        "el job quedó en {0!r}".format(jobs_repo.get(job_id)["status"])
    )


def test_a_finished_job_marks_the_project_as_done(job_manager, jobs_repo, projects_repo, project):
    stages = []

    def runner(ctx):
        ctx.stage("transcribing")
        stages.append(ctx.job_id)
        ctx.stage("rendering")

    job = job_manager.submit(project["id"], runner)
    finished = _wait_for(jobs_repo, job["id"], (job_states.DONE, job_states.FAILED))

    assert finished["status"] == job_states.DONE
    assert finished["stage"] == "finished"
    assert finished["stage_label"] == "Finalizado"
    assert finished["completed_at"]
    assert stages == [job["id"]]
    assert projects_repo.get(project["id"])["status"] == project_states.DONE


def test_stage_updates_are_visible_while_it_runs(job_manager, jobs_repo, project):
    reached = threading.Event()
    release = threading.Event()

    def runner(ctx):
        ctx.stage("transcribing", "Transcribiendo el audio")
        reached.set()
        release.wait(TIMEOUT)

    job = job_manager.submit(project["id"], runner)
    assert reached.wait(TIMEOUT)

    running = jobs_repo.get(job["id"])
    assert running["status"] == job_states.PROCESSING
    assert running["stage"] == "transcribing"
    assert running["message"] == "Transcribiendo el audio"
    assert running["started_at"]

    release.set()
    _wait_for(jobs_repo, job["id"], (job_states.DONE,))


def test_progress_stays_empty_when_there_is_no_real_percentage(job_manager, jobs_repo, project):
    def runner(ctx):
        ctx.stage("transcribing")

    job = job_manager.submit(project["id"], runner)
    finished = _wait_for(jobs_repo, job["id"], (job_states.DONE,))

    assert finished["progress"] is None


def test_a_known_error_reaches_the_person_as_it_was_written(
    job_manager, jobs_repo, projects_repo, project
):
    def runner(ctx):
        raise AppError("No pudimos descargar este video.", detail="yt-dlp 403")

    job = job_manager.submit(project["id"], runner)
    failed = _wait_for(jobs_repo, job["id"], (job_states.FAILED,))

    assert failed["error"] == "No pudimos descargar este video."
    assert projects_repo.get(project["id"])["status"] == project_states.FAILED


def test_an_unexpected_crash_does_not_leak_internals(job_manager, jobs_repo, project):
    def runner(ctx):
        raise ZeroDivisionError("division by zero")

    job = job_manager.submit(project["id"], runner)
    failed = _wait_for(jobs_repo, job["id"], (job_states.FAILED,))

    assert "ZeroDivisionError" not in failed["error"]
    assert failed["error"].startswith("El procesamiento se interrumpió")


def test_the_worker_survives_a_crashed_job(job_manager, jobs_repo, projects_repo, project):
    def broken(ctx):
        raise ZeroDivisionError()

    first = job_manager.submit(project["id"], broken)
    _wait_for(jobs_repo, first["id"], (job_states.FAILED,))

    second_project = projects_repo.create(
        source="https://www.youtube.com/watch?v=def", source_type="url", settings=OPTIONS
    )
    second = job_manager.submit(second_project["id"], lambda ctx: None)

    assert _wait_for(jobs_repo, second["id"], (job_states.DONE,))["status"] == job_states.DONE


def test_only_one_heavy_job_at_a_time(job_manager, jobs_repo, projects_repo, project):
    release = threading.Event()
    started = threading.Event()

    def slow(ctx):
        started.set()
        release.wait(TIMEOUT)

    job_manager.submit(project["id"], slow)
    assert started.wait(TIMEOUT)

    other = projects_repo.create(
        source="https://www.youtube.com/watch?v=def", source_type="url", settings=OPTIONS
    )
    with pytest.raises(JobBusy):
        job_manager.submit(other["id"], lambda ctx: None)

    release.set()


def test_cancelling_a_running_job_stops_it(job_manager, jobs_repo, projects_repo, project):
    started = threading.Event()
    hook_called = threading.Event()

    def runner(ctx):
        ctx.on_cancel(hook_called.set)
        started.set()
        for _ in range(200):
            ctx.raise_if_cancelled()
            threading.Event().wait(0.02)

    job = job_manager.submit(project["id"], runner)
    assert started.wait(TIMEOUT)

    job_manager.cancel(job["id"])
    cancelled = _wait_for(jobs_repo, job["id"], (job_states.CANCELLED,))

    assert cancelled["status"] == job_states.CANCELLED
    assert hook_called.is_set()  # el hook mata el subproceso del pipeline
    assert projects_repo.get(project["id"])["status"] == project_states.CANCELLED


def test_cancelling_a_queued_job_never_runs_it(job_manager, jobs_repo, projects_repo, project):
    release = threading.Event()
    ran = threading.Event()

    def blocker(ctx):
        release.wait(TIMEOUT)

    blocking_job = job_manager.submit(project["id"], blocker)

    # Encolamos a mano para saltear la validación de "ya hay uno en curso".
    other = projects_repo.create(
        source="https://www.youtube.com/watch?v=def", source_type="url", settings=OPTIONS
    )
    queued = jobs_repo.create(other["id"])
    jobs_repo.update(queued["id"], status=job_states.QUEUED)
    job_manager._queue.put(
        {"job_id": queued["id"], "project_id": other["id"], "runner": lambda ctx: ran.set()}
    )

    job_manager.cancel(queued["id"])
    release.set()
    _wait_for(jobs_repo, blocking_job["id"], (job_states.DONE,))

    assert jobs_repo.get(queued["id"])["status"] == job_states.CANCELLED
    assert not ran.is_set()


def test_cancelling_a_finished_job_changes_nothing(job_manager, jobs_repo, project):
    job = job_manager.submit(project["id"], lambda ctx: None)
    _wait_for(jobs_repo, job["id"], (job_states.DONE,))

    assert job_manager.cancel(job["id"])["status"] == job_states.DONE


def test_interrupted_jobs_are_closed_on_the_next_start(jobs_repo, project):
    job = jobs_repo.create(project["id"])
    jobs_repo.update(job["id"], status=job_states.PROCESSING)

    closed = jobs_repo.reset_orphans()

    assert closed == 1
    reopened = jobs_repo.get(job["id"])
    assert reopened["status"] == job_states.FAILED
    assert "se cerró la aplicación" in reopened["error"]
