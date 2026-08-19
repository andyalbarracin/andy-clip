"""Configuración de Andy Clip y su precedencia.

Precedencia, de mayor a menor (documentada también en `docs/ARCHITECTURE.md`):

    1. configuración guardada por la aplicación  (.local/settings.json)
    2. variables de entorno                      (las mismas que usa el core)
    3. defaults del código

`.local/settings.json` guarda **solo** los campos que la persona tocó desde la
UI. Lo que no está ahí sigue resolviéndose por env var, así que quien prefiera
manejar el proyecto con un `.env` no pierde nada al abrir la aplicación.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator

from .errors import ConfigurationError, PathValidationError
from .paths import LOCAL_DIR, PROJECT_ROOT, ensure_within

APP_NAME = "Andy Clip"
APP_VERSION = "0.1.0"

PROVIDERS: Tuple[str, ...] = ("openai", "gemini")

# Nombre visible de cada proveedor, en un solo lugar.
PROVIDER_LABELS: Dict[str, str] = {
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "muapi": "MuAPI",
}

MODES: Tuple[str, ...] = ("local", "muapi")
ASPECT_RATIOS: Tuple[str, ...] = ("9:16", "1:1", "4:5")
RESOLUTIONS: Tuple[str, ...] = ("360", "480", "720", "1080")
WHISPER_MODELS: Tuple[str, ...] = ("tiny", "base", "small", "medium", "large-v3")
WHISPER_DEVICES: Tuple[str, ...] = ("auto", "cpu", "cuda")

# Cómo se lleva un video horizontal al formato vertical.
FRAMINGS: Tuple[str, ...] = ("faces", "center", "fit")
BACKGROUNDS: Tuple[str, ...] = ("blur", "color", "gradient")

MAX_CLIPS = 10


# ─────────────────────────────────────────────────────────────────────────────
# Validaciones compartidas
#
# Viven sueltas para que la configuración global y las opciones de un proyecto
# apliquen exactamente las mismas reglas.
# ─────────────────────────────────────────────────────────────────────────────

def _one_of(value: Any, allowed: Tuple[str, ...], what: str) -> str:
    value = str(value or "").strip()
    if value not in allowed:
        raise ValueError(
            "{0} no soportado: {1!r}. Elegí entre {2}.".format(what, value, ", ".join(allowed))
        )
    return value


def validate_mode(value: str) -> str:
    return _one_of(str(value or "").lower(), MODES, "Modo")


def validate_provider(value: str) -> str:
    return _one_of(str(value or "").lower(), PROVIDERS, "Proveedor de IA")


def validate_aspect_ratio(value: str) -> str:
    return _one_of(value, ASPECT_RATIOS, "Relación de aspecto")


def validate_resolution(value: Any) -> str:
    return _one_of(str(value or "").strip().replace("p", ""), RESOLUTIONS, "Resolución")


def validate_whisper_model(value: str) -> str:
    return _one_of(value, WHISPER_MODELS, "Modelo de Whisper")


def validate_device(value: str) -> str:
    return _one_of(str(value or "").lower(), WHISPER_DEVICES, "Dispositivo")


def validate_framing(value: str) -> str:
    return _one_of(str(value or "").lower(), FRAMINGS, "Encuadre")


def validate_background(value: str) -> str:
    return _one_of(str(value or "").lower(), BACKGROUNDS, "Fondo")


def validate_color(value: str) -> str:
    """Un color hexadecimal. Va a parar a un comando de FFmpeg."""
    value = str(value or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("El color tiene que ser hexadecimal, por ejemplo #101112.")
    return value


def validate_num_clips(value: int) -> int:
    if value < 1 or value > MAX_CLIPS:
        raise ValueError("La cantidad de clips tiene que estar entre 1 y {0}.".format(MAX_CLIPS))
    return value


def validate_language(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip().lower()
    if not value or value in ("auto", "detect"):
        return None
    # ISO-639-1 (es, en) con variante regional opcional (pt-br).
    if len(value) > 5 or not value.replace("-", "").isalpha():
        raise ValueError("Código de idioma inválido: {0!r}.".format(value))
    return value


# ─────────────────────────────────────────────────────────────────────────────
# Modelos
# ─────────────────────────────────────────────────────────────────────────────

class AISettings(BaseModel):
    provider: str = "openai"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-3.6-flash"

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, value: str) -> str:
        return validate_provider(value)

    @field_validator("openai_model", "gemini_model")
    @classmethod
    def _check_model(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("El modelo no puede quedar vacío.")
        if len(value) > 120:
            raise ValueError("El nombre del modelo es demasiado largo.")
        return value


class TranscriptionSettings(BaseModel):
    whisper_model: str = "base"
    device: str = "auto"
    vad_filter: bool = False
    language: Optional[str] = None  # None = detectar automáticamente

    @field_validator("whisper_model")
    @classmethod
    def _check_whisper_model(cls, value: str) -> str:
        return validate_whisper_model(value)

    @field_validator("device")
    @classmethod
    def _check_device(cls, value: str) -> str:
        return validate_device(value)

    @field_validator("language")
    @classmethod
    def _check_language(cls, value: Optional[str]) -> Optional[str]:
        return validate_language(value)


class VideoSettings(BaseModel):
    aspect_ratio: str = "9:16"
    num_clips: int = 3
    resolution: str = "720"
    output_dir: str = "output"
    framing: str = "faces"
    background: str = "blur"
    background_color: str = "#0A0B0C"

    @field_validator("framing")
    @classmethod
    def _check_framing(cls, value: str) -> str:
        return validate_framing(value)

    @field_validator("background")
    @classmethod
    def _check_background(cls, value: str) -> str:
        return validate_background(value)

    @field_validator("background_color")
    @classmethod
    def _check_background_color(cls, value: str) -> str:
        return validate_color(value)

    @field_validator("aspect_ratio")
    @classmethod
    def _check_aspect_ratio(cls, value: str) -> str:
        return validate_aspect_ratio(value)

    @field_validator("resolution")
    @classmethod
    def _check_resolution(cls, value: str) -> str:
        return validate_resolution(value)

    @field_validator("num_clips")
    @classmethod
    def _check_num_clips(cls, value: int) -> int:
        return validate_num_clips(value)

    @field_validator("output_dir")
    @classmethod
    def _check_output_dir(cls, value: str) -> str:
        value = (value or "").strip() or "output"
        # Anti path traversal: la carpeta de resultados vive dentro del proyecto.
        try:
            ensure_within(PROJECT_ROOT, value)
        except PathValidationError as exc:
            # Pydantic solo envuelve ValueError; lo traducimos para que el error
            # llegue como ConfigurationError con el mensaje en castellano.
            raise ValueError(exc.message) from exc
        return value


class AnalysisSettings(BaseModel):
    """Parámetros del análisis. Solo lectura en V1: los define el core."""

    ideal_duration_seconds: Tuple[int, int] = (45, 90)
    long_video_threshold_seconds: int = 1800
    chunk_size_seconds: int = 1200
    chunk_overlap_seconds: int = 60
    max_llm_attempts: int = 3


class AppSettings(BaseModel):
    mode: str = "local"
    ai: AISettings = Field(default_factory=AISettings)
    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        return validate_mode(value)

    def resolved_output_dir(self) -> Path:
        return ensure_within(PROJECT_ROOT, self.video.output_dir)


class ProcessingOptions(BaseModel):
    """Opciones con las que se procesa **un** proyecto.

    Salen de la configuración global y la persona puede pisarlas en el
    formulario de "Nuevo proyecto". Se guardan junto al proyecto para que el
    resultado quede explicado por sus propias opciones y no por la config que
    haya en ese momento.
    """

    mode: str = "local"
    num_clips: int = 3
    aspect_ratio: str = "9:16"
    resolution: str = "720"
    language: Optional[str] = None
    framing: str = "faces"
    background: str = "blur"
    background_color: str = "#0A0B0C"

    @field_validator("framing")
    @classmethod
    def _check_framing(cls, value: str) -> str:
        return validate_framing(value)

    @field_validator("background")
    @classmethod
    def _check_background(cls, value: str) -> str:
        return validate_background(value)

    @field_validator("background_color")
    @classmethod
    def _check_background_color(cls, value: str) -> str:
        return validate_color(value)

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        return validate_mode(value)

    @field_validator("num_clips")
    @classmethod
    def _check_num_clips(cls, value: int) -> int:
        return validate_num_clips(value)

    @field_validator("aspect_ratio")
    @classmethod
    def _check_aspect_ratio(cls, value: str) -> str:
        return validate_aspect_ratio(value)

    @field_validator("resolution")
    @classmethod
    def _check_resolution(cls, value: str) -> str:
        return validate_resolution(value)

    @field_validator("language")
    @classmethod
    def _check_language(cls, value: Optional[str]) -> Optional[str]:
        return validate_language(value)


def processing_options_for(
    settings: AppSettings, overrides: Optional[Dict[str, Any]] = None
) -> ProcessingOptions:
    """Defaults de la configuración global + lo que la persona haya cambiado."""
    data: Dict[str, Any] = {
        "mode": settings.mode,
        "num_clips": settings.video.num_clips,
        "aspect_ratio": settings.video.aspect_ratio,
        "resolution": settings.video.resolution,
        "language": settings.transcription.language,
        "framing": settings.video.framing,
        "background": settings.video.background,
        "background_color": settings.video.background_color,
    }
    data.update({k: v for k, v in (overrides or {}).items() if v is not None})
    try:
        return ProcessingOptions.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError(_first_message(exc), detail=str(exc)) from exc


def analysis_settings() -> AnalysisSettings:
    """Leer los parámetros de análisis directamente del core, sin duplicarlos."""
    from app.engine import highlights as core_highlights

    return AnalysisSettings(
        long_video_threshold_seconds=core_highlights.LONG_VIDEO_THRESHOLD,
        chunk_size_seconds=core_highlights.CHUNK_SIZE_SECONDS,
        chunk_overlap_seconds=core_highlights.CHUNK_OVERLAP_SECONDS,
        max_llm_attempts=core_highlights.MAX_HIGHLIGHT_API_ATTEMPTS,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Precedencia
# ─────────────────────────────────────────────────────────────────────────────

def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _as_int(raw: str) -> int:
    return int(raw.strip())


def _as_str(raw: str) -> str:
    return raw.strip()


@dataclass(frozen=True)
class FieldSpec:
    """Un campo de configuración y de dónde puede venir su valor."""

    path: str
    env: Optional[str]
    cast: Callable[[str], Any]


FIELD_SPECS: Tuple[FieldSpec, ...] = (
    FieldSpec("mode", "ANDY_CLIP_MODE", _as_str),
    FieldSpec("ai.provider", "LLM_PROVIDER", _as_str),
    FieldSpec("ai.openai_model", "OPENAI_MODEL", _as_str),
    FieldSpec("ai.gemini_model", "GEMINI_MODEL", _as_str),
    FieldSpec("transcription.whisper_model", "LOCAL_WHISPER_MODEL", _as_str),
    FieldSpec("transcription.device", "LOCAL_WHISPER_DEVICE", _as_str),
    FieldSpec("transcription.vad_filter", "LOCAL_WHISPER_VAD_FILTER", _as_bool),
    FieldSpec("transcription.language", "LOCAL_WHISPER_LANGUAGE", _as_str),
    FieldSpec("video.aspect_ratio", "ANDY_CLIP_ASPECT_RATIO", _as_str),
    FieldSpec("video.num_clips", "ANDY_CLIP_NUM_CLIPS", _as_int),
    FieldSpec("video.resolution", "ANDY_CLIP_RESOLUTION", _as_str),
    FieldSpec("video.output_dir", "LOCAL_OUTPUT_DIR", _as_str),
    FieldSpec("video.framing", "ANDY_CLIP_FRAMING", _as_str),
    FieldSpec("video.background", "ANDY_CLIP_BACKGROUND", _as_str),
    FieldSpec("video.background_color", "ANDY_CLIP_BACKGROUND_COLOR", _as_str),
)


def _get_nested(data: Dict[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _has_nested(data: Dict[str, Any], path: str) -> bool:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _set_nested(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Merge recursivo: el patch pisa hoja por hoja, no rama por rama."""
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Store
# ─────────────────────────────────────────────────────────────────────────────

SETTINGS_FILENAME = "settings.json"


class SettingsStore:
    """Lee y escribe los overrides de configuración de la aplicación."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else (LOCAL_DIR / SETTINGS_FILENAME)

    # ── lectura ──────────────────────────────────────────────────────────────

    def read_overrides(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ConfigurationError(
                "No pudimos leer la configuración guardada.",
                detail="{0}: {1}".format(self.path, exc),
            ) from exc
        return raw if isinstance(raw, dict) else {}

    def resolve(self) -> AppSettings:
        """Aplicar la precedencia y validar el resultado."""
        overrides = self.read_overrides()
        return self._build(overrides)

    def sources(self) -> Dict[str, str]:
        """Para cada campo, de dónde salió el valor efectivo."""
        overrides = self.read_overrides()
        result: Dict[str, str] = {}
        for spec in FIELD_SPECS:
            if _has_nested(overrides, spec.path):
                result[spec.path] = "app"
            elif spec.env and os.environ.get(spec.env, "").strip():
                result[spec.path] = "env"
            else:
                result[spec.path] = "default"
        return result

    # ── escritura ────────────────────────────────────────────────────────────

    def update(self, patch: Dict[str, Any]) -> AppSettings:
        """Validar el patch contra la configuración completa y recién ahí guardar."""
        overrides = _merge(self.read_overrides(), patch)
        settings = self._build(overrides)  # levanta ConfigurationError si algo no cierra
        self._write(overrides)
        return settings

    def reset(self) -> AppSettings:
        """Volver a env vars + defaults."""
        if self.path.exists():
            self.path.unlink()
        return self.resolve()

    # ── internos ─────────────────────────────────────────────────────────────

    def _build(self, overrides: Dict[str, Any]) -> AppSettings:
        data: Dict[str, Any] = {}
        for spec in FIELD_SPECS:
            if _has_nested(overrides, spec.path):
                _set_nested(data, spec.path, _get_nested(overrides, spec.path))
                continue
            raw = os.environ.get(spec.env, "") if spec.env else ""
            if raw.strip():
                try:
                    _set_nested(data, spec.path, spec.cast(raw))
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError(
                        "La variable de entorno {0} tiene un valor inválido.".format(spec.env),
                        detail="{0}={1!r}: {2}".format(spec.env, raw, exc),
                    ) from exc
        try:
            return AppSettings.model_validate(data)
        except ValidationError as exc:
            raise ConfigurationError(
                _first_message(exc),
                detail=str(exc),
                action="settings",
            ) from exc

    def _write(self, overrides: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(overrides, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(str(tmp_path), str(self.path))


def _first_message(exc: ValidationError) -> str:
    """Sacar el mensaje en castellano que escribimos en el validator."""
    for error in exc.errors():
        message = str(error.get("msg", ""))
        # Pydantic prefija los ValueError propios con "Value error, ".
        if message.startswith("Value error, "):
            return message[len("Value error, "):]
        if message:
            return message
    return "La configuración no es válida."
