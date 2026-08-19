"""Proveedor Google Gemini, sobre el SDK `google-genai` que ya usa el core."""
from __future__ import annotations

from typing import List

from ...core.errors import DependencyMissingError
from .base import PING_PROMPT, ProviderTestResult, _safe_models, translate_provider_error

# Igual que en OpenAI: punto de partida del selector, reemplazable con
# "Actualizar modelos".
SUGGESTED_MODELS: List[str] = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]


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
        client = self._client()
        try:
            response = client.models.generate_content(
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
        # El cliente tiene que seguir vivo mientras se recorre el listado: lo
        # que devuelve `models.list()` es perezoso, y si el cliente se
        # recolecta antes de terminar de leerlo, cierra su conexión y el
        # recorrido explota con "the client has been closed".
        client = self._client()
        try:
            listing = list(client.models.list())
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
        # Se prueba generando, no listando. El listado incluye modelos que la
        # cuenta no puede usar: decía que todo estaba bien y después el
        # procesamiento fallaba con un 404 en la mitad.
        self.generate(PING_PROMPT)
        return ProviderTestResult(
            ok=True,
            message="Listo: el modelo «{0}» respondió.".format(self.model),
            models=_safe_models(self),
        )
