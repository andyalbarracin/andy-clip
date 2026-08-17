"""Cuerpos de request de la API de configuración.

Son parciales a propósito: la UI manda solo lo que la persona tocó, y
`exclude_unset` hace que el resto siga resolviéndose por env var o default.
`extra="forbid"` corta cualquier campo inventado antes de llegar al store.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIPatch(_Strict):
    provider: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_model: Optional[str] = None


class TranscriptionPatch(_Strict):
    whisper_model: Optional[str] = None
    device: Optional[str] = None
    vad_filter: Optional[bool] = None
    language: Optional[str] = None


class VideoPatch(_Strict):
    aspect_ratio: Optional[str] = None
    num_clips: Optional[int] = None
    resolution: Optional[str] = None
    output_dir: Optional[str] = None


class SettingsPatch(_Strict):
    mode: Optional[str] = None
    ai: Optional[AIPatch] = None
    transcription: Optional[TranscriptionPatch] = None
    video: Optional[VideoPatch] = None


class ApiKeyBody(_Strict):
    api_key: str = Field(min_length=1, max_length=500)
