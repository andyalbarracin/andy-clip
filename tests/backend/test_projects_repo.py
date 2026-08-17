"""Persistencia de proyectos, highlights y clips."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.errors import AppError
from app.models.projects import ProjectNotFound, default_project_name

OPTIONS = {"mode": "local", "num_clips": 3, "aspect_ratio": "9:16", "resolution": "720"}


def _create(repo, name=None):
    return repo.create(
        source="https://www.youtube.com/watch?v=abc",
        source_type="url",
        settings=OPTIONS,
        name=name,
    )


def test_default_name_reads_like_a_date():
    assert default_project_name(datetime(2026, 8, 17, 13, 30)) == "Video 17 ago 2026 - 13:30"


def test_create_stores_source_and_options(projects_repo):
    project = _create(projects_repo)

    assert project["source_type"] == "url"
    assert project["settings"]["num_clips"] == 3
    assert project["status"] == "draft"
    assert project["name"].startswith("Video ")


def test_get_unknown_project_is_a_404(projects_repo):
    with pytest.raises(ProjectNotFound):
        projects_repo.get("no-existe")


def test_list_returns_the_most_recently_updated_first(projects_repo):
    first = _create(projects_repo, name="Primero")
    second = _create(projects_repo, name="Segundo")
    projects_repo.rename(first["id"], "Primero editado")

    names = [p["name"] for p in projects_repo.list()]

    assert names[0] == "Primero editado"
    assert second["name"] in names
    assert projects_repo.count() == 2


def test_rename_trims_and_validates(projects_repo):
    project = _create(projects_repo)

    renamed = projects_repo.rename(project["id"], "  Mi   charla  ")
    assert renamed["name"] == "Mi charla"

    with pytest.raises(AppError):
        projects_repo.rename(project["id"], "   ")

    with pytest.raises(AppError):
        projects_repo.rename(project["id"], "x" * 200)


def test_delete_removes_the_project_from_the_history(projects_repo):
    project = _create(projects_repo)

    projects_repo.delete(project["id"])

    with pytest.raises(ProjectNotFound):
        projects_repo.get(project["id"])


def test_transcript_round_trips(projects_repo):
    project = _create(projects_repo)
    transcript = {"duration": 120.5, "segments": [{"start": 0, "end": 5, "text": "hola"}]}

    projects_repo.set_transcript(project["id"], transcript)

    stored = projects_repo.get(project["id"])
    assert stored["transcript"]["segments"][0]["text"] == "hola"
    assert stored["duration"] == 120.5


def test_highlights_are_ranked_and_marked_as_selected(projects_repo):
    project = _create(projects_repo)
    candidates = [
        {"title": "Flojo", "start_time": 0, "end_time": 30, "score": 40},
        {"title": "Buenísimo", "start_time": 60, "end_time": 120, "score": 95},
        {"title": "Bueno", "start_time": 200, "end_time": 260, "score": 70},
    ]

    stored = projects_repo.replace_highlights(project["id"], candidates, selected_count=2)

    assert [h["title"] for h in stored] == ["Buenísimo", "Bueno", "Flojo"]
    assert [h["selected"] for h in stored] == [True, True, False]
    assert stored[0]["duration"] == 60.0


def test_replacing_highlights_clears_the_previous_ones(projects_repo):
    project = _create(projects_repo)
    projects_repo.replace_highlights(
        project["id"], [{"title": "Viejo", "start_time": 0, "end_time": 10, "score": 10}], 1
    )

    projects_repo.replace_highlights(
        project["id"], [{"title": "Nuevo", "start_time": 0, "end_time": 10, "score": 10}], 1
    )

    assert [h["title"] for h in projects_repo.highlights(project["id"])] == ["Nuevo"]


def test_clips_keep_their_order_and_failures(projects_repo):
    project = _create(projects_repo)

    projects_repo.add_clip(project["id"], position=0, aspect_ratio="9:16", path="/tmp/a.mp4")
    projects_repo.add_clip(
        project["id"], position=1, aspect_ratio="9:16", status="failed", error="sin FFmpeg"
    )

    clips = projects_repo.clips(project["id"])
    assert len(clips) == 2
    assert clips[1]["status"] == "failed"
    assert clips[1]["path"] is None


def test_recent_clips_skip_the_ones_without_file(projects_repo):
    project = _create(projects_repo)
    projects_repo.add_clip(project["id"], position=0, aspect_ratio="9:16", path="/tmp/a.mp4")
    projects_repo.add_clip(project["id"], position=1, aspect_ratio="9:16", status="failed")

    recent = projects_repo.recent_clips()

    assert len(recent) == 1
    assert recent[0]["project_name"] == project["name"]


def test_deleting_a_project_cascades_to_highlights_and_clips(projects_repo):
    project = _create(projects_repo)
    projects_repo.replace_highlights(
        project["id"], [{"title": "H", "start_time": 0, "end_time": 10, "score": 50}], 1
    )
    projects_repo.add_clip(project["id"], position=0, aspect_ratio="9:16", path="/tmp/a.mp4")

    projects_repo.delete(project["id"])

    assert projects_repo.highlights(project["id"]) == []
    assert projects_repo.clips(project["id"]) == []
