"""Proveedor OpenAI.

Reproduce la llamada que ya hacía `app/engine/local/llm.py` para no
cambiar el comportamiento del motor: mismo endpoint, misma temperatura.
"""
from __future__ import annotations

from typing import List

from ...core.errors import DependencyMissingError
from .base import PING_PROMPT, ProviderTestResult, _safe_models, translate_provider_error

# Lista de arranque para el selector. No pretende estar completa ni actualizada:
# el botón "Actualizar modelos" consulta la API oficial y la reemplaza.
SUGGESTED_MODELS: List[str] = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"]

_EXCLUDED_MODEL_MARKERS = (
    "audio", "realtime", "transcribe", "tts", "whisper", "embedding",
    "image", "dall-e", "moderation", "sora", "codex",
)


class OpenAIProvider:
    name = "openai"
    label = "OpenAI"

    def __init__(self, api_key: str, model: str, timeout: float = 60.0) -> None:
        self._api_key = api_key
        self.model = model
        self._timeout = timeout

    # ── cliente ──────────────────────────────────────────────────────────────

    def _client(self):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise DependencyMissingError(
                "Falta el paquete de OpenAI en este entorno.",
                detail="pip install -r requirements-app.txt",
            ) from exc
        return OpenAI(api_key=self._api_key, timeout=self._timeout)

    # ── contrato ─────────────────────────────────────────────────────────────

    def generate(self, prompt: str) -> str:
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise translate_provider_error(exc, self.label) from exc
        return response.choices[0].message.content or ""

    def list_models(self) -> List[str]:
        try:
            listing = self._client().models.list()
        except Exception as exc:
            raise translate_provider_error(exc, self.label) from exc

        models = []
        for item in listing:
            model_id = getattr(item, "id", None) or ""
            if not model_id or not _looks_like_chat_model(model_id):
                continue
            models.append(model_id)
        return sorted(set(models))

    def test_connection(self) -> ProviderTestResult:
        # Se prueba generando, no listando: listar modelos es gratis y funciona
        # aunque la cuenta no tenga saldo, así que decía que todo estaba bien y
        # después el procesamiento fallaba por falta de crédito.
        self.generate(PING_PROMPT)
        return ProviderTestResult(
            ok=True,
            message="Listo: el modelo «{0}» respondió.".format(self.model),
            models=_safe_models(self),
        )


def _looks_like_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    if any(marker in lowered for marker in _EXCLUDED_MODEL_MARKERS):
        return False
    return lowered.startswith("gpt-") or lowered.startswith("o1") or lowered.startswith("o3") or lowered.startswith("o4")
