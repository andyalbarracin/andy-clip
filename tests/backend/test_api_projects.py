"""API de proyectos, clips y jobs."""
from __future__ import annotations

import uuid

import pytest

from app.core.paths import OUTPUT_DIR

YOUTUBE_URL = "https://www.youtube.com/watch?v=abc123"


def _create(client, **body):
    payload = {"source": YOUTUBE_URL}
    payload.update(body)
    return client.post("/api/projects", json=payload)


# ── alta ─────────────────────────────────────────────────────────────────────

def test_creating_a_project_uses_the_configured_defaults(client):
    response = _create(client)

    assert response.status_code == 201
    project = response.json()["project"]
    assert project["source_type"] == "url"
    assert project["status"] == "draft"
    assert project["settings"] == {
        "mode": "local",
        "num_clips": 3,
        "aspect_ratio": "9:16",
        "resolution": "720",
        "language": None,
        "framing": "faces",
        "background": "blur",
        "background_color": "#0A0B0C",
    }


def test_project_options_can_be_overridden_per_project(client):
    response = _create(client, options={"num_clips": 5, "aspect_ratio": "4:5", "language": "es"})

    settings = response.json()["project"]["settings"]
    assert settings["num_clips"] == 5
    assert settings["aspect_ratio"] == "4:5"
    assert settings["language"] == "es"
    assert settings["resolution"] == "720"  # lo que no se pisa viene de la config


def test_global_settings_feed_the_project_defaults(client):
    client.patch("/api/settings", json={"video": {"num_clips": 7, "resolution": "1080"}})

    settings = _create(client).json()["project"]["settings"]

    assert settings["num_clips"] == 7
    assert settings["resolution"] == "1080"


def test_an_invalid_source_is_rejected(client):
    response = _create(client, source="ftp://example.com/video.mp4")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_source"


def test_invalid_options_are_rejected(client):
    response = _create(client, options={"aspect_ratio": "16:9"})

    assert response.status_code == 400
    assert "16:9" in response.json()["error"]["message"]


def test_unknown_option_fields_are_rejected(client):
    assert _create(client, options={"codec": "av1"}).status_code == 422


# ── listado y detalle ────────────────────────────────────────────────────────

def test_listing_projects(client):
    _create(client)
    _create(client)

    body = client.get("/api/projects").json()

    assert body["total"] == 2
    assert len(body["projects"]) == 2


def test_reading_an_unknown_project_is_a_404(client):
    response = client.get("/api/projects/no-existe")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_detail_includes_highlights_clips_and_job(client):
    project_id = _create(client).json()["project"]["id"]

    body = client.get("/api/projects/{0}".format(project_id)).json()

    assert body["highlights"] == []
    assert body["clips"] == []
    assert body["job"] is None


def test_renaming_a_project(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.patch(
        "/api/projects/{0}".format(project_id), json={"name": "Charla sobre hábitos"}
    )

    assert response.json()["project"]["name"] == "Charla sobre hábitos"


def test_renaming_with_an_empty_name_is_rejected(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.patch("/api/projects/{0}".format(project_id), json={"name": "   "})

    assert response.status_code in (400, 422)


def test_deleting_a_project_keeps_the_files(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.delete("/api/projects/{0}".format(project_id))

    assert response.json()["files_kept"] is True
    assert client.get("/api/projects/{0}".format(project_id)).status_code == 404


def test_transcript_is_empty_before_processing(client):
    project_id = _create(client).json()["project"]["id"]

    body = client.get("/api/projects/{0}/transcript".format(project_id)).json()

    assert body["segments"] == []


# ── inicio ───────────────────────────────────────────────────────────────────

def test_home_returns_everything_the_first_screen_needs(client):
    _create(client)

    body = client.get("/api/home").json()

    assert body["total_projects"] == 1
    assert len(body["recent_projects"]) == 1
    assert body["recent_clips"] == []
    assert {c["id"] for c in body["system"]} >= {"ffmpeg", "openai", "gemini"}
    assert body["local_mode"]["ready"] is False


def test_home_is_empty_but_valid_on_a_fresh_install(client):
    body = client.get("/api/home").json()

    assert body["total_projects"] == 0
    assert body["recent_projects"] == []


# ── jobs ─────────────────────────────────────────────────────────────────────

def test_stages_are_exposed_in_order(client):
    stages = client.get("/api/jobs/stages").json()["stages"]

    assert stages[0] == {"id": "preparing", "label": "Preparando fuente"}
    assert stages[-1]["label"] == "Finalizado"


def test_no_active_jobs_on_a_fresh_install(client):
    body = client.get("/api/jobs/active").json()

    assert body["busy"] is False
    assert body["jobs"] == []


def test_reading_an_unknown_job_is_a_404(client):
    assert client.get("/api/jobs/no-existe").status_code == 404


# ── archivo de un clip ───────────────────────────────────────────────────────

@pytest.fixture
def clip_file():
    """Un mp4 de mentira dentro de output/, borrado al terminar."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "test-{0}.mp4".format(uuid.uuid4().hex[:8])
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    yield path
    path.unlink(missing_ok=True)


def test_serving_a_clip_file(client, projects_repo, clip_file):
    project_id = _create(client).json()["project"]["id"]
    clip = projects_repo.add_clip(
        project_id, position=0, aspect_ratio="9:16", path=str(clip_file)
    )

    response = client.get("/api/clips/{0}/file".format(clip["id"]))

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"


def test_a_clip_path_outside_the_project_is_refused(client, projects_repo, tmp_path):
    project_id = _create(client).json()["project"]["id"]
    outside = tmp_path / "ajeno.mp4"
    outside.write_bytes(b"\x00")
    clip = projects_repo.add_clip(
        project_id, position=0, aspect_ratio="9:16", path=str(outside)
    )

    response = client.get("/api/clips/{0}/file".format(clip["id"]))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_path"


def test_a_clip_without_file_is_a_404(client, projects_repo):
    project_id = _create(client).json()["project"]["id"]
    clip = projects_repo.add_clip(
        project_id, position=0, aspect_ratio="9:16", status="failed"
    )

    assert client.get("/api/clips/{0}/file".format(clip["id"])).status_code == 404


# ── poner a procesar ─────────────────────────────────────────────────────────

def test_processing_without_an_api_key_points_at_configuration(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.post("/api/projects/{0}/process".format(project_id))

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] in ("missing_credential", "dependency_missing")
    if error["code"] == "missing_credential":
        assert error["action"] == "settings/ai"


def test_processing_queues_a_job(client, monkeypatch):
    from app.api.routes import projects as projects_routes

    monkeypatch.setattr(projects_routes, "build_runner", lambda *a, **k: lambda ctx: None)
    project_id = _create(client).json()["project"]["id"]

    response = client.post("/api/projects/{0}/process".format(project_id))

    assert response.status_code == 202
    job = response.json()["job"]
    assert job["project_id"] == project_id
    assert job["status"] in ("queued", "processing", "done")


def test_only_one_video_processes_at_a_time(client, monkeypatch):
    import threading

    from app.api.routes import projects as projects_routes

    release = threading.Event()
    monkeypatch.setattr(
        projects_routes,
        "build_runner",
        lambda *a, **k: lambda ctx: release.wait(5),
    )

    first = _create(client).json()["project"]["id"]
    second = _create(client).json()["project"]["id"]
    client.post("/api/projects/{0}/process".format(first))

    response = client.post("/api/projects/{0}/process".format(second))
    release.set()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_busy"


def test_processing_an_unknown_project_is_a_404(client):
    assert client.post("/api/projects/no-existe/process").status_code == 404


# ── la interfaz servida ──────────────────────────────────────────────────────

def test_the_html_is_never_cached(client):
    """El index.html nombra los archivos compilados: uno viejo deja la app sin estilos."""
    response = client.get("/")

    if response.status_code == 503:
        return  # la interfaz no está compilada en este entorno

    assert "no-store" in response.headers.get("cache-control", "")


# ── editor: volver a generar con otros ajustes ───────────────────────────────

def test_rerendering_updates_the_saved_options(client, projects_repo, monkeypatch):
    from app.api.routes import projects as projects_routes

    monkeypatch.setattr(projects_routes, "build_render_runner", lambda *a, **k: lambda ctx: None)
    project_id = _create(client).json()["project"]["id"]

    response = client.post(
        "/api/projects/{0}/rerender".format(project_id),
        json={"framing": "fit", "background": "gradient"},
    )

    assert response.status_code == 202
    settings = client.get("/api/projects/{0}".format(project_id)).json()["project"]["settings"]
    assert settings["framing"] == "fit"
    assert settings["background"] == "gradient"
    # Lo que no se tocó queda como estaba.
    assert settings["num_clips"] == 3


def test_rerendering_rejects_an_invalid_framing(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.post(
        "/api/projects/{0}/rerender".format(project_id), json={"framing": "zoom"}
    )

    assert response.status_code in (400, 422)


def test_rerendering_without_the_original_video_explains_why(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.post(
        "/api/projects/{0}/rerender".format(project_id), json={"framing": "fit"}
    )

    assert response.status_code == 400
    assert "video original" in response.json()["error"]["message"]


def test_an_unknown_api_route_answers_404_whatever_the_method(client):
    """Un 405 manda a buscar el problema al lugar equivocado."""
    for pedir in (client.post, client.put, client.patch, client.delete):
        response = pedir("/api/no-existe")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


# ── editor: video original y recorte de momentos ─────────────────────────────

def test_the_source_video_is_served_for_previewing(client, projects_repo, clip_file):
    project_id = _create(client).json()["project"]["id"]
    projects_repo.set_media_path(project_id, str(clip_file))

    response = client.get("/api/projects/{0}/media".format(project_id))

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"


def test_without_the_source_video_the_preview_says_so(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.get("/api/projects/{0}/media".format(project_id))

    assert response.status_code == 400
    assert "video original" in response.json()["error"]["message"]


def _momento(client, projects_repo, project_id):
    projects_repo.replace_highlights(
        project_id,
        [{"title": "Momento", "start_time": 10.0, "end_time": 40.0, "score": 90}],
        selected_count=1,
    )
    return projects_repo.highlights(project_id)[0]


def test_trimming_moves_the_in_and_out_points(client, projects_repo):
    project_id = _create(client).json()["project"]["id"]
    momento = _momento(client, projects_repo, project_id)

    response = client.patch(
        "/api/projects/{0}/highlights/{1}".format(project_id, momento["id"]),
        json={"start_time": 12.5, "end_time": 33.0},
    )

    assert response.status_code == 200
    editado = response.json()["highlights"][0]
    assert editado["start_time"] == 12.5
    assert editado["end_time"] == 33.0
    assert editado["duration"] == 20.5


def test_trimming_only_one_end_keeps_the_other(client, projects_repo):
    project_id = _create(client).json()["project"]["id"]
    momento = _momento(client, projects_repo, project_id)

    response = client.patch(
        "/api/projects/{0}/highlights/{1}".format(project_id, momento["id"]),
        json={"end_time": 25.0},
    )

    editado = response.json()["highlights"][0]
    assert editado["start_time"] == 10.0
    assert editado["end_time"] == 25.0


def test_a_clip_cannot_end_before_it_starts(client, projects_repo):
    project_id = _create(client).json()["project"]["id"]
    momento = _momento(client, projects_repo, project_id)

    response = client.patch(
        "/api/projects/{0}/highlights/{1}".format(project_id, momento["id"]),
        json={"start_time": 30.0, "end_time": 20.0},
    )

    assert response.status_code == 400
    assert "posterior" in response.json()["error"]["message"]


def test_a_moment_can_be_left_out_of_the_render(client, projects_repo):
    project_id = _create(client).json()["project"]["id"]
    momento = _momento(client, projects_repo, project_id)

    response = client.patch(
        "/api/projects/{0}/highlights/{1}".format(project_id, momento["id"]),
        json={"selected": False},
    )

    assert response.json()["highlights"][0]["selected"] is False


def test_editing_an_unknown_moment_is_a_404(client):
    project_id = _create(client).json()["project"]["id"]

    response = client.patch(
        "/api/projects/{0}/highlights/no-existe".format(project_id),
        json={"selected": True},
    )

    assert response.status_code == 404
