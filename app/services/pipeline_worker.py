"""El procesamiento pesado, en su propio proceso.

Corre aparte del servidor por tres razones concretas:

* el motor lee su configuración **al importarse**, así que un proceso nuevo con
  el entorno ya resuelto es la única forma de que un cambio de ajustes tenga
  efecto sin reiniciar todo;
* transcribir y recodificar bloquean el intérprete durante minutos, y el
  servidor tiene que seguir contestando;
* cancelar de verdad es matar un proceso, no pedirle amablemente a un hilo que
  se detenga.

Se comunica con el servidor por su salida estándar, una línea JSON por evento.

    python -m app.services.pipeline_worker --source ... --out-dir ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List


def emit(event: str, **payload: Any) -> None:
    """Una línea JSON por evento. El servidor la lee y actualiza el trabajo."""
    sys.stdout.write(json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _download_message(exc: Exception) -> str:
    """Traducir un fallo de descarga a algo que se pueda accionar.

    yt-dlp falla por muchos motivos distintos y su texto es para
    desarrolladores. Estos son los casos que aparecen de verdad.
    """
    detail = str(exc).lower()

    # El orden importa: varios mensajes de YouTube contienen "sign in", así que
    # los casos específicos van antes que los generales.
    if "the page needs to be reloaded" in detail or "nsig" in detail or "player" in detail:
        return (
            "YouTube cambió su sitio y la herramienta de descarga quedó vieja. "
            "Hay que actualizar yt-dlp, que necesita Python 3.10 o superior."
        )
    if "age" in detail or "edad" in detail:
        return "Ese video tiene restricción de edad y no lo podemos descargar."
    if "your country" in detail or "copyright" in detail or "blocked" in detail:
        return "Ese video está bloqueado en tu país o por derechos de autor."
    if "private" in detail or "sign in" in detail or "log in" in detail or "login" in detail:
        return "Ese video es privado o pide iniciar sesión, así que no lo podemos descargar."
    if "unavailable" in detail or "removed" in detail or "not available" in detail:
        return "Ese video ya no está disponible en la plataforma."
    if "no space" in detail:
        return "No queda espacio en el disco para descargar el video."
    if "network" in detail or "timed out" in detail or "connection" in detail:
        return "Se cortó la conexión mientras descargábamos el video. Probá de nuevo."

    return (
        "No pudimos descargar este video. La URL puede ser privada, estar "
        "restringida o no ser compatible."
    )


def run(args: argparse.Namespace) -> int:
    # Importar acá adentro: así un fallo de dependencias sale como evento de
    # error y no como un traceback suelto antes de que nadie esté escuchando.
    from app.engine.highlights import get_highlights
    from app.engine.local.clipper import crop_clip_local
    from app.engine.local.downloader import download_youtube_local
    from app.engine.local.llm import call_local_llm
    from app.engine.local.transcriber import transcribe_local

    os.makedirs(args.out_dir, exist_ok=True)

    emit("stage", stage="downloading")
    try:
        source_path = download_youtube_local(args.source, fmt=args.resolution, out_dir=args.out_dir)
    except Exception as exc:  # noqa: BLE001 - traducimos, no escondemos
        emit("error", message=_download_message(exc), detail=str(exc))
        return 1
    emit("source", path=source_path)

    emit("stage", stage="transcribing")
    transcript = transcribe_local(source_path, language=args.language or None)
    if not transcript["segments"]:
        emit(
            "error",
            message="No encontramos voz en este video, así que no hay nada que analizar.",
        )
        return 1
    emit("transcript", transcript=transcript)

    emit("stage", stage="analyzing")
    result = get_highlights(transcript, num_clips=args.num_clips, llm_fn=call_local_llm)
    candidates: List[Dict[str, Any]] = result.get("highlights", [])
    if not candidates:
        emit(
            "error",
            message="La IA no encontró momentos destacables en este video.",
        )
        return 1

    emit("stage", stage="selecting")
    chosen = sorted(candidates, key=lambda h: int(h.get("score", 0)), reverse=True)[
        : args.num_clips
    ]
    emit("highlights", highlights=candidates, selected=len(chosen))

    emit("stage", stage="rendering")
    for index, highlight in enumerate(chosen, start=1):
        emit(
            "stage",
            stage="reframing" if index > 1 else "rendering",
            message="Generando video {0} de {1}".format(index, len(chosen)),
            progress=(index - 1) / len(chosen),
        )
        out_path = os.path.join(args.out_dir, "clip_{0:02d}.mp4".format(index))
        try:
            crop_clip_local(
                source_path,
                float(highlight["start_time"]),
                float(highlight["end_time"]),
                args.aspect_ratio,
                out_path,
            )
        except Exception as exc:  # noqa: BLE001 - un clip roto no cancela el resto
            emit(
                "clip",
                position=index - 1,
                path=None,
                status="failed",
                error=str(exc),
                start_time=highlight["start_time"],
                end_time=highlight["end_time"],
            )
            continue

        emit(
            "clip",
            position=index - 1,
            path=out_path,
            status="done",
            start_time=highlight["start_time"],
            end_time=highlight["end_time"],
            duration=float(highlight["end_time"]) - float(highlight["start_time"]),
        )

    emit("done")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Procesamiento de un proyecto de Andy Clip")
    parser.add_argument("--source", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--num-clips", type=int, default=3)
    parser.add_argument("--aspect-ratio", default="9:16")
    parser.add_argument("--resolution", default="720")
    parser.add_argument("--language", default="")
    args = parser.parse_args()

    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - el detalle va al servidor, no al usuario
        emit("error", message="No pudimos completar el procesamiento.", detail=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
