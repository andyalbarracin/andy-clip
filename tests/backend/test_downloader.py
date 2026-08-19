"""Descarga con reintentos por cliente. Sin red: se simula yt-dlp."""
from __future__ import annotations

import pytest

from app.engine.local import downloader


@pytest.fixture(autouse=True)
def fake_ytdlp(monkeypatch):
    """yt-dlp presente pero inerte: cada test define qué hace la descarga."""
    monkeypatch.setattr(downloader, "_import_ytdlp", lambda: object())


def test_the_first_client_that_works_wins(monkeypatch):
    intentos = []

    def attempt(_ytdlp, url, fmt, out_dir, client):
        intentos.append(client)
        if client in ("default", "android"):
            raise RuntimeError("HTTP Error 403: Forbidden")
        return "/tmp/video.mp4"

    monkeypatch.setattr(downloader, "_attempt_download", attempt)

    assert downloader.download_youtube_local("https://youtu.be/abc") == "/tmp/video.mp4"
    assert intentos == ["default", "android", "ios"]


def test_it_does_not_keep_trying_after_success(monkeypatch):
    intentos = []

    def attempt(_ytdlp, url, fmt, out_dir, client):
        intentos.append(client)
        return "/tmp/video.mp4"

    monkeypatch.setattr(downloader, "_attempt_download", attempt)
    downloader.download_youtube_local("https://youtu.be/abc")

    assert intentos == ["default"]


def test_when_every_client_fails_it_reports_the_last_error(monkeypatch):
    def attempt(_ytdlp, url, fmt, out_dir, client):
        raise RuntimeError("falló con {0}".format(client))

    monkeypatch.setattr(downloader, "_attempt_download", attempt)

    with pytest.raises(RuntimeError) as excinfo:
        downloader.download_youtube_local("https://youtu.be/abc")

    assert "mweb" in str(excinfo.value)


def test_the_client_order_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LOCAL_YTDLP_CLIENTS", "android, tv")

    assert downloader._player_clients() == ["android", "tv"]


def test_a_local_file_never_touches_the_network(tmp_path, monkeypatch):
    """Un archivo del equipo se devuelve tal cual: no hay descarga que fallar."""
    def explode(*args, **kwargs):
        raise AssertionError("no se debería intentar descargar")

    monkeypatch.setattr(downloader, "_attempt_download", explode)
    video = tmp_path / "charla.mp4"
    video.write_bytes(b"\x00")

    assert downloader.download_youtube_local(str(video)) == str(video.resolve())
