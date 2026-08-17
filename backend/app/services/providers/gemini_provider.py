"""Proveedor Google Gemini, sobre el SDK `google-genai` que ya usa el core."""
from __future__ import annotations

from typing import List

from ...core.errors import DependencyMissingError
from .base import ProviderTestResult, translate_provider_error

# Igual que en OpenAI: punto de partida del selector, reemplazable con
# "Actualizar modelos".
SUGGESTED_MODELS: List[str] = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]


class GeminiProvider:
    name = "gemini"
    label = "Google Gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    # ── cliente ──────────────────────────────────────────────────────────────

    def _client(self):
        try:
            from google import genai  # type: ignore
        except ImportError as exc:
            raise DependencyMissingError(
                "Falta el paquete google-genai en este entorno.",
                detail="pip install -r requirements-app.txt",
            ) from exc
        return genai.Client(api_key=self._api_key)

    # ── contrato ─────────────────────────────────────────────────────────────

    def generate(self, prompt: str) -> str:
        try:
            response = self._client().models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                    "max_output_tokens": 8192,
                },
            )
        except Exception as exc:
            raise translate_provider_error(exc, self.label) from exc
        return response.text or ""

    def list_models(self) -> List[str]:
        try:
            listing = self._client().models.list()
        except Exception as exc:
            raise translate_provider_error(exc, self.label) from exc

        models = []
        for item in listing:
            name = getattr(item, "name", None) or ""
            if not name:
                continue
            actions = getattr(item, "supported_actions", None)
            # Cuando el SDK no informa acciones no lo descartamos: preferimos
            # ofrecer de más antes que esconder un modelo válido.
            if actions and "generateContent" not in actions:
                continue
            models.append(name.split("/")[-1])
        return sorted(set(models))

    def test_connection(self) -> ProviderTestResult:
        models = self.list_models()
        if models and self.model not in models:
            return ProviderTestResult(
                ok=True,
                message=(
                    "Conectamos con Gemini, pero el modelo «{0}» no aparece entre los "
                    "disponibles para esta API key.".format(self.model)
                ),
                models=models,
            )
        return ProviderTestResult(
            ok=True,
            message="Conectamos con Gemini. El modelo «{0}» está disponible.".format(self.model),
            models=models,
        )
