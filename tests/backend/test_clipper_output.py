"""El clip que sale tiene que poder reproducirse en la propia aplicación.

El motor escribía el video reencuadrado con códec mp4v y después copiaba ese
stream: los navegadores no lo reproducen. Este test genera un video de prueba
con FFmpeg —sin descargar nada, sin llamar a nadie— y comprueba que el
resultado sea H.264 con la relación de aspecto pedida.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="hace falta FFmpeg para generar y medir el video de prueba",
)


def _make_source(path, seconds=2):
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=15",
            "-f", "lavfi", "-i", "sine=frequency=440",
            "-t", str(seconds),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(path),
        ],
        check=True,
    )
    return path


def _probe(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,codec_type,width,height",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["streams"]


def test_the_clip_comes_out_playable_and_vertical(tmp_path):
    from app.engine.local.clipper import crop_clip_local

    source = _make_source(tmp_path / "fuente.mp4")
    out_path = tmp_path / "clip.mp4"

    crop_clip_local(str(source), 0.2, 1.4, "9:16", str(out_path))

    streams = {s["codec_type"]: s for s in _probe(out_path)}

    # H.264: es lo que reproduce cualquier navegador. mp4v no.
    assert streams["video"]["codec_name"] == "h264"
    # El audio viaja con el clip.
    assert streams["audio"]["codec_name"] == "aac"
    # 9:16 sobre un cuadro de 360 de alto → 202x360 (par).
    assert streams["video"]["height"] == 360
    assert abs(streams["video"]["width"] / streams["video"]["height"] - 9 / 16) < 0.02


def test_no_temporary_files_are_left_behind(tmp_path):
    from app.engine.local.clipper import crop_clip_local

    source = _make_source(tmp_path / "fuente.mp4")
    out_path = tmp_path / "clip.mp4"

    crop_clip_local(str(source), 0.0, 1.0, "1:1", str(out_path))

    leftovers = [p.name for p in tmp_path.iterdir() if ".cut." in p.name or ".silent." in p.name]
    assert leftovers == []


def _pixel(path, x, y, width):
    """El color de un píxel del primer cuadro, para comprobar el relleno."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    offset = (y * width + x) * 3
    return tuple(raw[offset:offset + 3])


def test_fitting_keeps_the_whole_frame_inside_the_canvas(tmp_path):
    """Recortar se come los zócalos y los subtítulos quemados; esto no."""
    from app.engine.local.clipper import crop_clip_local

    source = _make_source(tmp_path / "fuente.mp4")
    out_path = tmp_path / "clip.mp4"

    crop_clip_local(str(source), 0.1, 1.2, "9:16", str(out_path), framing="fit", width=720)

    video = {s["codec_type"]: s for s in _probe(out_path)}["video"]
    assert (video["width"], video["height"]) == (720, 1280)
    assert video["codec_name"] == "h264"


def test_the_solid_background_is_the_colour_that_was_asked_for(tmp_path):
    from app.engine.local.clipper import crop_clip_local

    source = _make_source(tmp_path / "fuente.mp4")
    out_path = tmp_path / "clip.mp4"

    crop_clip_local(
        str(source), 0.1, 1.2, "9:16", str(out_path),
        framing="fit", background="color", background_color="#204080", width=720,
    )

    # La franja de arriba tiene que ser el color pedido, con tolerancia por la
    # compresión del video.
    r, g, b = _pixel(out_path, x=10, y=10, width=720)
    assert abs(r - 0x20) < 12 and abs(g - 0x40) < 12 and abs(b - 0x80) < 12


def test_cropping_and_fitting_produce_different_shapes(tmp_path):
    from app.engine.local.clipper import crop_clip_local

    source = _make_source(tmp_path / "fuente.mp4")
    recortado = tmp_path / "recortado.mp4"
    completo = tmp_path / "completo.mp4"

    crop_clip_local(str(source), 0.1, 1.2, "9:16", str(recortado), framing="center")
    crop_clip_local(str(source), 0.1, 1.2, "9:16", str(completo), framing="fit", width=720)

    corte = {s["codec_type"]: s for s in _probe(recortado)}["video"]
    entero = {s["codec_type"]: s for s in _probe(completo)}["video"]

    # El recorte hereda el alto de la fuente; el completo usa el lienzo pedido.
    assert corte["height"] == 360
    assert entero["height"] == 1280


def test_every_framing_mode_produces_a_playable_clip(tmp_path):
    from app.engine.local.clipper import crop_clip_local

    source = _make_source(tmp_path / "fuente.mp4")

    for framing, background in (
        ("faces", "blur"), ("center", "blur"),
        ("fit", "blur"), ("fit", "color"), ("fit", "gradient"),
    ):
        out_path = tmp_path / f"{framing}_{background}.mp4"
        crop_clip_local(
            str(source), 0.1, 1.0, "9:16", str(out_path),
            framing=framing, background=background, width=720,
        )
        streams = {s["codec_type"]: s for s in _probe(out_path)}
        assert streams["video"]["codec_name"] == "h264"
        assert "audio" in streams
