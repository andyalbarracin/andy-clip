"""Configuración de la aplicación y de los proveedores de IA.

Las únicas rutas que hacen una llamada real a un proveedor son `/test` y
`/models`, y solo se ejecutan cuando la persona las pide desde la UI.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Path

from ...core.errors import AppError, ConfigurationError
from ...core.secrets import ENV_VARS, SECRET_PROVIDERS, SecretsService
from ...core.settings import (
    ASPECT_RATIOS,
    BACKGROUNDS,
    FRAMINGS,
    MAX_CLIPS,
    MODES,
    PROVIDERS,
    RESOLUTIONS,
    WHISPER_DEVICES,
    WHISPER_MODELS,
    SettingsStore,
    analysis_settings,
)
from ...services.providers import SUGGESTED_MODELS, build_provider
from ...services.providers.registry import LABELS, model_for
from ...schemas.settings import ApiKeyBody, SettingsPatch
from ..deps import get_secrets, get_settings_store

router = APIRouter(prefix="/settings", tags=["configuración"])

# Proveedores con implementación de LLM. MuAPI guarda credencial pero todavía
# no expone "Probar conexión" ni listado de modelos.
TESTABLE_PROVIDERS = PROVIDERS


def _options() -> Dict[str, Any]:
    """Valores permitidos, para que el frontend no los duplique."""
    return {
        "modes": list(MODES),
        "providers": [{"id": p, "label": LABELS[p]} for p in PROVIDERS],
        "aspect_ratios": list(ASPECT_RATIOS),
        "resolutions": list(RESOLUTIONS),
        "whisper_models": list(WHISPER_MODELS),
        "whisper_devices": list(WHISPER_DEVICES),
        "framings": [
            {"id": "faces", "label": "Recortar siguiendo las caras"},
            {"id": "center", "label": "Recortar por el centro"},
            {"id": "fit", "label": "Video completo, con relleno"},
        ],
        "backgrounds": [
            {"id": "blur", "label": "Desenfoque del propio video"},
            {"id": "gradient", "label": "Degradado del propio video"},
            {"id": "color", "label": "Color sólido"},
        ],
        "max_clips": MAX_CLIPS,
        "suggested_models": SUGGESTED_MODELS,
    }


def _payload(store: SettingsStore) -> Dict[str, Any]:
    return {
        "settings": store.resolve().model_dump(),
        "sources": store.sources(),
        "options": _options(),
        "analysis": analysis_settings().model_dump(),
    }


@router.get("")
def read_settings(store: SettingsStore = Depends(get_settings_store)) -> Dict[str, Any]:
    return _payload(store)


@router.patch("")
def update_settings(
    patch: SettingsPatch,
    store: SettingsStore = Depends(get_settings_store),
) -> Dict[str, Any]:
    data = patch.model_dump(exclude_unset=True)
    if not data:
        raise ConfigurationError("No mandaste ningún cambio para guardar.")
    store.update(data)
    return _payload(store)


@router.post("/reset")
def reset_settings(store: SettingsStore = Depends(get_settings_store)) -> Dict[str, Any]:
    store.reset()
    return _payload(store)


# ── Proveedores de IA ────────────────────────────────────────────────────────

def _provider_id(provider: str) -> str:
    provider = (provider or "").strip().lower()
    if provider not in SECRET_PROVIDERS:
        raise ConfigurationError("Proveedor desconocido: {0!r}.".format(provider))
    return provider


def _ai_payload(store: SettingsStore, secrets: SecretsService) -> Dict[str, Any]:
    settings = store.resolve()
    status = secrets.status()
    providers = []
    for provider in SECRET_PROVIDERS:
        entry: Dict[str, Any] = {
            "id": provider,
            "label": LABELS[provider],
            "configured": status[provider]["configured"],
            "masked_key": status[provider]["masked"],
            "key_source": status[provider]["source"],
            "env_var": ENV_VARS[provider],
            "testable": provider in TESTABLE_PROVIDERS,
        }
        if provider in PROVIDERS:
            entry["model"] = model_for(settings, provider)
            entry["suggested_models"] = SUGGESTED_MODELS[provider]
        providers.append(entry)

    return {"default_provider": settings.ai.provider, "providers": providers}


@router.get("/ai")
def read_ai_settings(
    store: SettingsStore = Depends(get_settings_store),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    return _ai_payload(store, secrets)


@router.put("/ai/{provider}/key")
def save_api_key(
    body: ApiKeyBody,
    provider: str = Path(...),
    store: SettingsStore = Depends(get_settings_store),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    """Guardar la key. La response nunca incluye el valor completo."""
    secrets.set(_provider_id(provider), body.api_key)
    return _ai_payload(store, secrets)


@router.delete("/ai/{provider}/key")
def delete_api_key(
    provider: str = Path(...),
    store: SettingsStore = Depends(get_settings_store),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    secrets.delete(_provider_id(provider))
    return _ai_payload(store, secrets)


@router.post("/ai/{provider}/test")
def test_provider_connection(
    provider: str = Path(...),
    store: SettingsStore = Depends(get_settings_store),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    """Llamada real al proveedor — solo cuando la persona pulsa "Probar conexión"."""
    provider_id = _provider_id(provider)
    if provider_id not in TESTABLE_PROVIDERS:
        raise AppError(
            "Todavía no podemos probar la conexión con {0} desde acá.".format(
                LABELS.get(provider_id, provider_id)
            ),
            detail="test_connection not implemented for provider={0}".format(provider_id),
        )
    result = build_provider(store.resolve(), secrets, provider=provider_id).test_connection()
    return {"ok": result.ok, "message": result.message, "models": result.models}


@router.post("/ai/{provider}/models")
def refresh_provider_models(
    provider: str = Path(...),
    store: SettingsStore = Depends(get_settings_store),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    """Llamada real al proveedor — solo cuando la persona pulsa "Actualizar modelos"."""
    provider_id = _provider_id(provider)
    if provider_id not in TESTABLE_PROVIDERS:
        raise AppError(
            "No hay listado de modelos disponible para {0}.".format(
                LABELS.get(provider_id, provider_id)
            ),
            detail="list_models not implemented for provider={0}".format(provider_id),
        )
    models = build_provider(store.resolve(), secrets, provider=provider_id).list_models()
    return {"models": models}
