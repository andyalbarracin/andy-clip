"""Local clipping: ffmpeg subclip + OpenCV face-aware vertical crop.

Two stages per highlight:
  1. Cut the source video to [start, end] with ffmpeg (re-encoded, audio kept).
  2. Reframe the cut to the target aspect ratio. For 9:16 we slide a vertical
     window horizontally across the frame to keep faces centred (Haar
     cascade — same approach as the original repo, no external models).
"""
import os
import subprocess
from typing import Dict, List, Optional, Tuple

from ..config import LOCAL_OUTPUT_DIR


def _ratio(aspect_ratio: str) -> float:
    """Parse '9:16' → 9/16, '1:1' → 1.0."""
    try:
        w, h = aspect_ratio.split(":")
        return float(w) / float(h)
    except (ValueError, ZeroDivisionError):
        return 9.0 / 16.0


def _cut_subclip(source_path: str, start: float, end: float, out_path: str) -> str:
    """Cut [start, end] out of the source into a re-encoded mp4 with audio.

    `-ss` goes *before* `-i` so ffmpeg seeks to the start instead of decoding
    the whole file from zero on every clip, and `-t` states a duration, which
    is unambiguous after a seek.
    """
    duration = max(0.05, end - start)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}",
        "-i", source_path,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path


def _even(value: float) -> int:
    """Los códecs de video piden dimensiones pares."""
    number = max(2, int(round(value)))
    return number - (number % 2)


def _canvas(aspect_ratio: str, width: int) -> Tuple[int, int]:
    """El lienzo final: el ancho lo elegís vos, el alto sale de la proporción."""
    canvas_w = _even(width)
    return canvas_w, _even(canvas_w / _ratio(aspect_ratio))


def _fit_with_background(
    in_path: str,
    out_path: str,
    aspect_ratio: str,
    background: str,
    color: str,
    width: int,
) -> str:
    """Meter el cuadro completo dentro del formato, rellenando lo que sobra.

    Recortar a vertical se come los costados, y con eso los zócalos y los
    subtítulos que el video ya trae quemados. Acá no se recorta nada: el video
    entra entero y arriba y abajo se rellena.

    Todo en una sola pasada de FFmpeg, sin OpenCV: es bastante más rápido que
    el reencuadre que sigue caras.
    """
    canvas_w, canvas_h = _canvas(aspect_ratio, width)
    scaled = f"[0:v]scale={canvas_w}:-2[fg]"

    if background == "color":
        # Sin fondo derivado del video: un color plano y listo.
        filtergraph = (
            f"[0:v]scale={canvas_w}:-2,"
            f"pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color={color}[v]"
        )
    elif background == "gradient":
        # Un degradado hecho con los propios colores del video: se lo reduce a
        # unos pocos píxeles y se lo vuelve a agrandar.
        filtergraph = (
            f"[0:v]scale=4:4,scale={canvas_w}:{canvas_h}:flags=bicubic,"
            f"gblur=sigma=60,eq=brightness=-0.05[bg];{scaled};"
            f"[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v]"
        )
    else:  # blur
        # El clásico: una copia del propio video, ampliada y desenfocada. Se
        # oscurece apenas para que el cuadro real se despegue del fondo.
        sigma = max(12, canvas_w // 24)
        filtergraph = (
            f"[0:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},gblur=sigma={sigma},eq=brightness=-0.08[bg];{scaled};"
            f"[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v]"
        )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", in_path,
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path


def _load_face_detector(cv2_module):
    """El detector de caras Haar, si esta instalación de OpenCV lo trae.

    OpenCV 5 sacó `CascadeClassifier` del paquete principal. Cuando no está,
    devolvemos `None` y el recorte queda centrado: peor encuadre, pero el clip
    se genera igual en vez de fallar.
    """
    if not hasattr(cv2_module, "CascadeClassifier"):
        return None

    data_dir = getattr(getattr(cv2_module, "data", None), "haarcascades", "")
    detector = cv2_module.CascadeClassifier(data_dir + "haarcascade_frontalface_default.xml")
    return None if detector.empty() else detector


def _reframe_vertical(
    in_path: str, out_path: str, aspect_ratio: str, track_faces: bool = True
) -> str:
    """Crop the cut clip to the target aspect ratio, tracking faces if possible."""
    try:
        import cv2  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "opencv-python is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    target_ratio = _ratio(aspect_ratio)
    cap = cv2.VideoCapture(in_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open {in_path}")

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Compute the largest crop that fits inside the frame at the target ratio.
    if target_ratio < src_w / src_h:
        crop_h = src_h
        crop_w = int(crop_h * target_ratio)
    else:
        crop_w = src_w
        crop_h = int(crop_w / target_ratio)
    crop_w = max(2, crop_w - (crop_w % 2))
    crop_h = max(2, crop_h - (crop_h % 2))

    face_detector = _load_face_detector(cv2) if track_faces else None
    if track_faces and face_detector is None:
        print(
            "[clip/local] sin detector de caras disponible: recorte centrado",
            flush=True,
        )

    silent_path = out_path + ".silent.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(silent_path, fourcc, fps, (crop_w, crop_h))

    last_center: Optional[Tuple[int, int]] = None
    smoothing = 0.15  # how aggressively to chase a new face position
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        faces = ()
        if face_detector is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_detector.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
            )
        if len(faces) > 0:
            # Pick the largest face — usually the speaker.
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            cx = x + w // 2
            cy = y + h // 2
            if last_center is None:
                last_center = (cx, cy)
            else:
                lx, ly = last_center
                last_center = (
                    int(lx + (cx - lx) * smoothing),
                    int(ly + (cy - ly) * smoothing),
                )
        if last_center is None:
            last_center = (src_w // 2, src_h // 2)

        cx, cy = last_center
        x0 = max(0, min(src_w - crop_w, cx - crop_w // 2))
        y0 = max(0, min(src_h - crop_h, cy - crop_h // 2))
        cropped = frame[y0:y0 + crop_h, x0:x0 + crop_w]
        writer.write(cropped)

    cap.release()
    writer.release()

    # Mux the audio back onto the reframed video.
    #
    # OpenCV writes mp4v, which browsers refuse to play — copying that stream
    # would produce a file the app itself can't preview. Re-encoding to H.264
    # costs a little CPU and makes the clip playable everywhere.
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", silent_path,
        "-i", in_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "1:a:0?",
        "-shortest",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    os.remove(silent_path)
    return out_path


# Cómo se lleva el video al formato vertical.
FRAMING_FACES = "faces"    # recorta siguiendo las caras
FRAMING_CENTER = "center"  # recorta por el centro
FRAMING_FIT = "fit"        # entra entero y se rellena arriba y abajo

DEFAULT_BACKGROUND = "blur"
DEFAULT_BACKGROUND_COLOR = "#0A0B0C"
DEFAULT_WIDTH = 720


def crop_clip_local(
    source_path: str,
    start_time: float,
    end_time: float,
    aspect_ratio: str,
    out_path: str,
    framing: str = FRAMING_FACES,
    background: str = DEFAULT_BACKGROUND,
    background_color: str = DEFAULT_BACKGROUND_COLOR,
    width: int = DEFAULT_WIDTH,
) -> str:
    """Cut + reframe one highlight, returning the local mp4 path."""
    cut_path = out_path + ".cut.mp4"
    try:
        _cut_subclip(source_path, start_time, end_time, cut_path)
        if framing == FRAMING_FIT:
            _fit_with_background(
                cut_path, out_path, aspect_ratio, background, background_color, width
            )
        else:
            _reframe_vertical(
                cut_path, out_path, aspect_ratio, track_faces=(framing == FRAMING_FACES)
            )
    finally:
        if os.path.exists(cut_path):
            os.remove(cut_path)
    return out_path


def crop_highlights_local(
    source_path: str,
    highlights: List[Dict],
    aspect_ratio: str = "9:16",
    out_dir: Optional[str] = None,
    framing: str = FRAMING_FACES,
    background: str = DEFAULT_BACKGROUND,
    background_color: str = DEFAULT_BACKGROUND_COLOR,
    width: int = DEFAULT_WIDTH,
) -> List[Dict]:
    out_dir = out_dir or LOCAL_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    results: List[Dict] = []
    for i, h in enumerate(highlights, 1):
        out_path = os.path.join(out_dir, f"short_{i:02d}.mp4")
        print(f"[clip/local] {i}/{len(highlights)}: {h.get('title', '(untitled)')}", flush=True)
        try:
            crop_clip_local(
                source_path,
                float(h["start_time"]),
                float(h["end_time"]),
                aspect_ratio,
                out_path,
                framing=framing,
                background=background,
                background_color=background_color,
                width=width,
            )
            results.append({**h, "clip_url": out_path})
        except Exception as e:
            print(f"[clip/local] {i} failed: {e}", flush=True)
            results.append({**h, "clip_url": None, "error": str(e)})
    return results
