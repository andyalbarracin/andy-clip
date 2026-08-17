"""Puesta en marcha del procesamiento. Sin video, sin FFmpeg y sin llamadas pagas."""
from __future__ import annotations

import json

import pytest

from app.core.errors import AppError, DependencyMissingError, MissingCredentialError
from app.services import pipeline
from app.services.diagnostics import AVAILABLE, NOT_DETECTED, Component

FAKE_KEY = "sk-test-0000000000000000000000004F2A"

OPTIONS = {
    "mode": "local",
    "num_clips": 2,
    "aspect_ratio": "9:16",
    "resolution": "720",
    "language": None,
}


@pytest.fixture
def project(projects_repo):
    return projects_repo.create(
        source="https://www.youtube.com/watch?v=abc",
        source_type="url",
        settings=OPTIONS,
    )


@pytest.fixture
def with_ffmpeg(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "ffmpeg_status",
        lambda: Component(id="ffmpeg", label="FFmpeg", status=AVAILABLE, version="7.0"),
    )


# ── qué se comprueba antes de encolar ────────────────────────────────────────

def test_without_an_api_key_it_refuses_to_start(
    project, projects_repo, settings_store, secrets_service, with_ffmpeg
):
    with pytest.raises(MissingCredentialError):
        pipeline.build_runner(project, settings_store.resolve(), secrets_service, projects_repo)


def test_without_ffmpeg_it_says_so_before_queueing(
    project, projects_repo, settings_store, secrets_service, monkeypatch
):
    secrets_service.set("openai", FAKE_KEY)
    monkeypatch.setattr(
        pipeline,
        "ffmpeg_status",
        lambda: Component(id="ffmpeg", label="FFmpeg", status=NOT_DETECTED),
    )

    with pytest.raises(DependencyMissingError) as excinfo:
        pipeline.build_runner(project, settings_store.resolve(), secrets_service, projects_repo)

    assert "FFmpeg" in excinfo.value.message


def test_muapi_mode_is_not_runnable_from_the_app_yet(
    projects_repo, settings_store, secrets_service, with_ffmpeg
):
    secrets_service.set("openai", FAKE_KEY)
    project = projects_repo.create(
        source="https://youtu.be/abc",
        source_type="url",
        settings={**OPTIONS, "mode": "muapi"},
    )

    with pytest.raises(AppError) as excinfo:
        pipeline.build_runner(project, settings_store.resolve(), secrets_service, projects_repo)

    assert "modo local" in excinfo.value.message


def test_the_child_only_gets_the_key_of_the_chosen_provider(
    settings_store, secrets_service, monkeypatch
):
    secrets_service.set("openai", FAKE_KEY)
    secrets_service.set("gemini", "otra-clave-distinta")
    settings_store.update({"ai": {"provider": "openai"}})

    env = pipeline._child_env(
        settings_store.resolve(),
        secrets_service,
        pipeline.ProcessingOptions.model_validate(OPTIONS),
    )

    assert env["OPENAI_API_KEY"] == FAKE_KEY
    assert env.get("GEMINI_API_KEY") is None
    assert env["LLM_PROVIDER"] == "openai"


def test_each_project_writes_to_its_own_folder(project):
    other = pipeline.project_output_dir("otro-proyecto")

    assert pipeline.project_output_dir(project["id"]).name == project["id"]
    assert other != pipeline.project_output_dir(project["id"])


# ── eventos del proceso hijo ─────────────────────────────────────────────────

class FakeContext:
    def __init__(self):
        self.stages = []
        self.cancelled = False

    def stage(self, stage, message=None, progress=None):
        self.stages.append((stage, message, progress))

    def raise_if_cancelled(self):
        pass


def _event(**payload):
    return json.dumps(payload) + "\n"


def test_a_stage_event_moves_the_job(project, projects_repo):
    ctx = FakeContext()

    pipeline._handle_event(
        _event(event="stage", stage="transcribing", message="Transcribiendo"),
        ctx, project["id"], projects_repo,
    )

    assert ctx.stages == [("transcribing", "Transcribiendo", None)]


def test_the_transcript_is_stored(project, projects_repo):
    transcript = {"duration": 90.0, "segments": [{"start": 0, "end": 5, "text": "hola"}]}

    pipeline._handle_event(
        _event(event="transcript", transcript=transcript),
        FakeContext(), project["id"], projects_repo,
    )

    stored = projects_repo.get(project["id"])
    assert stored["transcript"]["segments"][0]["text"] == "hola"
    assert stored["duration"] == 90.0


def test_highlights_are_stored_with_the_chosen_ones_marked(project, projects_repo):
    highlights = [
        {"title": "A", "start_time": 0, "end_time": 30, "score": 90},
        {"title": "B", "start_time": 60, "end_time": 90, "score": 50},
        {"title": "C", "start_time": 120, "end_time": 150, "score": 10},
    ]

    pipeline._handle_event(
        _event(event="highlights", highlights=highlights, selected=2),
        FakeContext(), project["id"], projects_repo,
    )

    stored = projects_repo.highlights(project["id"])
    assert [h["selected"] for h in stored] == [True, True, False]


def test_a_clip_is_linked_to_the_moment_it_came_from(project, projects_repo):
    pipeline._handle_event(
        _event(
            event="highlights",
            highlights=[{"title": "A", "start_time": 12.5, "end_time": 60, "score": 90}],
            selected=1,
        ),
        FakeContext(), project["id"], projects_repo,
    )

    pipeline._handle_event(
        _event(event="clip", position=0, path="/tmp/clip_01.mp4", status="done",
               start_time=12.5, end_time=60, duration=47.5),
        FakeContext(), project["id"], projects_repo,
    )

    clip = projects_repo.clips(project["id"])[0]
    assert clip["path"] == "/tmp/clip_01.mp4"
    assert clip["highlight_id"] == projects_repo.highlights(project["id"])[0]["id"]


def test_a_failed_clip_is_recorded_without_a_file(project, projects_repo):
    pipeline._handle_event(
        _event(event="clip", position=0, path=None, status="failed",
               error="ffmpeg falló", start_time=0, end_time=10),
        FakeContext(), project["id"], projects_repo,
    )

    clip = projects_repo.clips(project["id"])[0]
    assert clip["status"] == "failed"
    assert clip["path"] is None


def test_an_error_event_returns_the_message_for_the_person(project, projects_repo):
    message = pipeline._handle_event(
        _event(event="error", message="No encontramos voz en este video.", detail="whisper: 0 segments"),
        FakeContext(), project["id"], projects_repo,
    )

    assert message == "No encontramos voz en este video."


def test_noise_from_the_engine_is_ignored(project, projects_repo):
    assert pipeline._handle_event(
        "[download/local] bajando el video...\n", FakeContext(), project["id"], projects_repo
    ) is None
