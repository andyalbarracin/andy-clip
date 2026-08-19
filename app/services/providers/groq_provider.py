"""Proveedor Groq.

Groq expone la misma API que OpenAI, así que reusa el mismo cliente cambiando
la dirección base. Existe acá como tercera red de contención: si el proveedor
principal se queda sin saldo o te limita, el procesamiento puede seguir.
"""
from __future__ import annotations

from typing import List

from .openai_provider import OpenAIProvider

BASE_URL = "https://api.groq.com/openai/v1"

# Punto de partida del selector. `qwen` queda afuera a propósito: devuelve su
# razonamiento antes del JSON y el analizador de momentos se confunde.
SUGGESTED_MODELS: List[str] = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound-mini",
]

_EXCLUDED = ("whisper", "tts", "guard", "vision", "prompt", "orpheus", "qwen")


class GroqProvider(OpenAIProvider):
    name = "groq"
    label = "Groq"
    base_url = BASE_URL

    def list_models(self) -> List[str]:
        from .base import translate_provider_error

        try:
            listing = self._client().models.list()
        except Exception as exc:
            raise translate_provider_error(exc, self.label) from exc

        return sorted(
            model_id
            for model_id in (getattr(item, "id", "") for item in listing)
            if model_id and not any(marker in model_id.lower() for marker in _EXCLUDED)
        )
