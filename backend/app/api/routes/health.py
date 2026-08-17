"""Health y estado del sistema. Nunca dispara una llamada paga."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ...core.secrets import SecretsService
from ...core.settings import APP_NAME, APP_VERSION, SettingsStore
from ...services import diagnostics
from ..deps import get_secrets, get_settings_store

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health(
    store: SettingsStore = Depends(get_settings_store),
    secrets: SecretsService = Depends(get_secrets),
) -> Dict[str, Any]:
    """La app abre siempre, con o sin API keys configuradas."""
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "mode": store.resolve().mode,
        "local_mode": diagnostics.local_mode_is_ready(secrets),
    }


@router.get("/system/status")
def system_status(secrets: SecretsService = Depends(get_secrets)) -> Dict[str, Any]:
    return {
        "components": [c.as_dict() for c in diagnostics.system_components(secrets)],
        "local_mode": diagnostics.local_mode_is_ready(secrets),
    }


@router.get("/system/summary")
def system_summary(secrets: SecretsService = Depends(get_secrets)) -> Dict[str, Any]:
    """Estado discreto para el Inicio."""
    return {
        "components": [c.as_dict() for c in diagnostics.home_components(secrets)],
        "local_mode": diagnostics.local_mode_is_ready(secrets),
    }
