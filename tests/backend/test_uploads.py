"""Subida de un video del equipo."""
from __future__ import annotations

from app.api.routes.uploads import UPLOADS_DIR


def _cleanup(path):
    from pathlib import Path

    Path(path).unlink(missing_ok=True)


def test_uploading_a_video_returns_a_usable_path(client):
    response = client.post(
        "/api/uploads",
        files={"file": ("charla.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "charla.mp4"
    assert body["size"] == 12
    assert body["path"].startswith(str(UPLOADS_DIR))
    _cleanup(body["path"])


def test_the_stored_name_never_comes_from_the_user(client):
    """El nombre original es texto del usuario: no se usa como nombre de archivo."""
    response = client.post(
        "/api/uploads",
        files={"file": ("../../../etc/passwd.mp4", b"\x00\x00", "video/mp4")},
    )

    body = response.json()
    assert ".." not in body["path"]
    assert "passwd" not in body["path"]
    assert body["path"].endswith(".mp4")
    _cleanup(body["path"])


def test_an_unsupported_format_is_rejected(client):
    response = client.post(
        "/api/uploads",
        files={"file": ("notas.txt", b"hola", "text/plain")},
    )

    assert response.status_code == 400
    assert "formato" in response.json()["error"]["message"]


def test_an_empty_file_is_rejected(client):
    response = client.post(
        "/api/uploads",
        files={"file": ("vacio.mp4", b"", "video/mp4")},
    )

    assert response.status_code == 400
    assert "vacío" in response.json()["error"]["message"]


def test_an_uploaded_file_is_accepted_as_a_project_source(client):
    upload = client.post(
        "/api/uploads",
        files={"file": ("charla.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
    ).json()

    response = client.post("/api/projects", json={"source": upload["path"]})

    assert response.status_code == 201
    assert response.json()["project"]["source_type"] == "file"
    _cleanup(upload["path"])
