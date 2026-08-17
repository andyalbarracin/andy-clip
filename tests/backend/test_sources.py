"""Validación de la fuente de un proyecto."""
from __future__ import annotations

import pytest

from app.services.sources import (
    SOURCE_FILE,
    SOURCE_URL,
    InvalidSourceError,
    classify_source,
)


def test_youtube_url_is_accepted():
    assert classify_source("https://www.youtube.com/watch?v=abc123") == (
        SOURCE_URL,
        "https://www.youtube.com/watch?v=abc123",
    )


def test_http_url_is_accepted():
    source_type, _ = classify_source("http://example.com/video.mp4")
    assert source_type == SOURCE_URL


def test_a_local_file_outside_the_project_is_allowed(tmp_path):
    """La frontera PROJECT_ROOT limita a Claude, no a quien usa la app."""
    video = tmp_path / "charla.mp4"
    video.write_bytes(b"\x00")

    source_type, resolved = classify_source(str(video))

    assert source_type == SOURCE_FILE
    assert resolved == str(video.resolve())


@pytest.mark.parametrize(
    "source",
    ["", "   ", "ftp://example.com/v.mp4", "javascript:alert(1)", "https://"],
)
def test_invalid_sources_are_rejected(source):
    with pytest.raises(InvalidSourceError):
        classify_source(source)


def test_relative_paths_are_rejected():
    with pytest.raises(InvalidSourceError) as excinfo:
        classify_source("videos/charla.mp4")

    assert "ruta completa" in excinfo.value.message


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(InvalidSourceError) as excinfo:
        classify_source(str(tmp_path / "no-existe.mp4"))

    assert "No encontramos" in excinfo.value.message


def test_unsupported_extension_is_reported(tmp_path):
    document = tmp_path / "notas.txt"
    document.write_text("hola", encoding="utf-8")

    with pytest.raises(InvalidSourceError):
        classify_source(str(document))


def test_a_directory_is_not_a_video(tmp_path):
    with pytest.raises(InvalidSourceError):
        classify_source(str(tmp_path))
