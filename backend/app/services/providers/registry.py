"""Armado de proveedores a partir de la configuración y los secrets."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from ...core.errors import ConfigurationError
from ...core.secrets import SecretsService
from ...core.settings import PROVIDER_LABELS, AppSettings
from .base import LLMProvider
from .gemini_provider import SUGGESTED_MODELS as GEMINI_SUGGESTED
from .gemini_provider import GeminiProvider
from .openai_provider import SUGGESTED_MODELS as OPENAI_SUGGESTED
from .openai_provider import OpenAIProvider

LABELS: Dict[str, str] = PROVIDER_LABELS

SUGGESTED_MODELS: Dict[str, List[str]] = {
    "openai": OPENAI_SUGGESTED,
    "gemini": GEMINI_SUGGESTED,
}


def model_for(settings: AppSettings, provider: str) -> str:
    if provider == "openai":
        return settings.ai.openai_model
    if provider == "gemini":
        return settings.ai.gemini_model
    raise ConfigurationError("Proveedor de IA desconocido: {0!r}.".format(provider))


def build_provider(
    settings: AppSettings,
    secrets: SecretsService,
    provider: Optional[str] = None,
) -> LLMProvider:
    """Instanciar el proveedor pedido (o el predeterminado) con su credencial.

    Levanta `MissingCredentialError` si falta la API key: es el único momento
    en que la ausencia de una key bloquea algo.
    """
    name = (provider or settings.ai.provider).strip().lower()
    api_key = secrets.require(name)
    model = model_for(settings, name)

    if name == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    if name == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    raise ConfigurationError("Proveedor de IA desconocido: {0!r}.".format(name))


def build_llm_fn(
    settings: AppSettings,
    secrets: SecretsService,
    provider: Optional[str] = None,
) -> Callable[[str], str]:
    """Puente hacia el core: `get_highlights(..., llm_fn=build_llm_fn(...))`.

    Mantiene el LLM pluggable tal como lo dejó upstream, sin acoplar el core a
    FastAPI ni a la configuración de la app.
    """
    llm_provider = build_provider(settings, secrets, provider)

    def llm_fn(prompt: str) -> str:
        return llm_provider.generate(prompt)

    return llm_fn
