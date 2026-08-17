"""Contrato común de los proveedores de IA.

El pipeline nunca habla con un SDK directamente:

    FastAPI → ProcessingService → LLMProvider → OpenAI / Gemini → core

El core sigue recibiendo una función `llm_fn(prompt) -> str` (así lo diseñó
así quedó diseñado), y `registry.build_llm_fn()` es el puente entre ambos mundos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

try:  # pragma: no cover - Protocol existe desde 3.8
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

from ...core.errors import ProviderAuthError, ProviderError


@dataclass
class ProviderTestResult:
    """Resultado de "Probar conexión". Nunca contiene la API key."""

    ok: bool
    message: str
    detail: Optional[str] = None
    models: List[str] = field(default_factory=list)


@runtime_checkable
class LLMProvider(Protocol):
    """Lo mínimo que Andy Clip le pide a un proveedor de IA."""

    name: str
    label: str

    def generate(self, prompt: str) -> str:
        """Devolver la respuesta del modelo como texto plano."""

    def test_connection(self) -> ProviderTestResult:
        """Validar credencial con el request más barato posible."""

    def list_models(self) -> List[str]:
        """Modelos disponibles para esta credencial."""


_AUTH_MARKERS = (
    "authentication",
    "permissiondenied",
    "unauthenticated",
    "invalid_api_key",
    "api key not valid",
    "invalid authentication",
)


def translate_provider_error(exc: Exception, label: str) -> ProviderError:
    """Convertir una excepción del SDK en un error con mensaje para la UI."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    haystack = "{0} {1}".format(type(exc).__name__, exc).lower()

    if status in (401, 403) or any(marker in haystack for marker in _AUTH_MARKERS):
        return ProviderAuthError(
            "{0} rechazó la API key configurada.".format(label),
            detail="{0}: {1}".format(type(exc).__name__, exc),
        )
    if status == 429 or "rate limit" in haystack or "quota" in haystack:
        return ProviderError(
            "{0} está limitando los pedidos o se agotó la cuota. Probá de nuevo en un rato.".format(label),
            detail="{0}: {1}".format(type(exc).__name__, exc),
        )
    if status == 404 or ("model" in haystack and "not found" in haystack):
        return ProviderError(
            "El modelo configurado no está disponible en {0}.".format(label),
            detail="{0}: {1}".format(type(exc).__name__, exc),
            action="settings/ai",
        )
    if "timeout" in haystack or "timed out" in haystack:
        return ProviderError(
            "{0} tardó demasiado en responder.".format(label),
            detail="{0}: {1}".format(type(exc).__name__, exc),
        )
    return ProviderError(
        "No pudimos conectarnos con {0}.".format(label),
        detail="{0}: {1}".format(type(exc).__name__, exc),
    )
