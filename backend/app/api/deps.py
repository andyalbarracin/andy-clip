"""Dependencias compartidas de la API.

Se resuelven por `Depends` para que los tests puedan reemplazarlas por
instancias apuntando a un directorio temporal (`app.dependency_overrides`).
"""
from __future__ import annotations

from functools import lru_cache

from ..core.secrets import SecretsService
from ..core.settings import AppSettings, SettingsStore


@lru_cache(maxsize=1)
def get_settings_store() -> SettingsStore:
    return SettingsStore()


@lru_cache(maxsize=1)
def get_secrets() -> SecretsService:
    return SecretsService()


def get_settings() -> AppSettings:
    return get_settings_store().resolve()
