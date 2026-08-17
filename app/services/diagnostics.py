"""Estado del sistema, sin llamadas pagas ni instalaciones.

Todo lo que hay acá es no destructivo: buscar binarios en el PATH, leer la
versión de un paquete instalado y preguntarle al `SecretsService` si una key
está cargada. Nunca se contacta a OpenAI, Gemini ni MuAPI para pintar estados:
eso pasa solo cuando la persona pulsa "Probar conexión".
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from ..core.secrets import SecretsService

# Estados posibles de un componente.
AVAILABLE = "available"          # Disponible
CONFIGURED = "configured"        # Configurado
NOT_CONFIGURED = "not_configured"  # No configurado
NOT_DETECTED = "not_detected"    # No detectado
ERROR = "error"                  # Error

BINARY_TIMEOUT_SECONDS = 5


@dataclass
class Component:
    id: str
    label: str
    status: str
    version: Optional[str] = None
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Optional[str]]:
        return asdict(self)


def _package_version(distribution: str) -> Optional[str]:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - Python < 3.8
        return None
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None
    except Exception:  # pragma: no cover - metadata corrupta
        return None


def _binary_version(binary: str, args: Optional[List[str]] = None) -> Component:
    path = shutil.which(binary)
    if not path:
        return Component(
            id=binary,
            label=binary,
            status=NOT_DETECTED,
            detail="No lo encontramos en el PATH de este equipo.",
        )
    try:
        completed = subprocess.run(
            [path] + (args or ["-version"]),
            capture_output=True,
            text=True,
            timeout=BINARY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Component(id=binary, label=binary, status=ERROR, detail=str(exc))

    first_line = (completed.stdout or completed.stderr or "").splitlines()
    return Component(
        id=binary,
        label=binary,
        status=AVAILABLE,
        version=first_line[0].strip() if first_line else None,
        detail=path,
    )


def ffmpeg_status() -> Component:
    component = _binary_version("ffmpeg")
    component.label = "FFmpeg"
    if component.status == NOT_DETECTED:
        component.detail = (
            "FFmpeg no está disponible en este equipo. Es necesario para generar "
            "clips localmente."
        )
    return component


def ffprobe_status() -> Component:
    component = _binary_version("ffprobe")
    component.label = "FFprobe"
    return component


def _python_package(component_id: str, label: str, distribution: str) -> Component:
    version = _package_version(distribution)
    if version is None:
        return Component(
            id=component_id,
            label=label,
            status=NOT_DETECTED,
            detail="Instalalo con: pip install -r requirements-app.txt",
        )
    return Component(id=component_id, label=label, status=AVAILABLE, version=version)


def _provider_component(
    component_id: str, label: str, secrets: SecretsService
) -> Component:
    status = secrets.status()[component_id]
    return Component(
        id=component_id,
        label=label,
        status=CONFIGURED if status["configured"] else NOT_CONFIGURED,
        detail=status["masked"],
    )


def python_status() -> Component:
    return Component(
        id="python",
        label="Python",
        status=AVAILABLE,
        version=platform.python_version(),
        detail=sys.executable,
    )


def system_components(secrets: SecretsService) -> List[Component]:
    """Todo lo que muestra Configuración › Diagnóstico."""
    return [
        python_status(),
        ffmpeg_status(),
        ffprobe_status(),
        _python_package("yt_dlp", "yt-dlp", "yt-dlp"),
        _python_package("faster_whisper", "faster-whisper", "faster-whisper"),
        _python_package("opencv", "OpenCV", "opencv-python"),
        _python_package("openai_sdk", "OpenAI SDK", "openai"),
        _python_package("google_genai_sdk", "Google GenAI SDK", "google-genai"),
        _provider_component("openai", "OpenAI", secrets),
        _provider_component("gemini", "Google Gemini", secrets),
        _provider_component("muapi", "MuAPI", secrets),
    ]


def home_components(secrets: SecretsService) -> List[Component]:
    """Versión reducida para el estado discreto del Inicio."""
    whisper = _python_package("faster_whisper", "Whisper", "faster-whisper")
    return [
        ffmpeg_status(),
        whisper,
        _provider_component("openai", "OpenAI", secrets),
        _provider_component("gemini", "Google Gemini", secrets),
        _provider_component("muapi", "MuAPI", secrets),
    ]


def local_mode_is_ready(secrets: SecretsService) -> Dict[str, object]:
    """¿Se puede procesar un video en modo local ahora mismo?"""
    missing: List[str] = []
    if ffmpeg_status().status != AVAILABLE:
        missing.append("FFmpeg")
    if _package_version("faster-whisper") is None:
        missing.append("faster-whisper")
    if not (secrets.has("openai") or secrets.has("gemini")):
        missing.append("un proveedor de IA")
    return {"ready": not missing, "missing": missing}
