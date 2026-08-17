"""Dependencias compartidas de la API.

Se resuelven por `Depends` para que los tests puedan reemplazarlas por
instancias apuntando a un directorio temporal (`app.dependency_overrides`).
Los repositorios se crean por request (son objetos vacíos que abren su propia
conexión); el `JobManager` no, porque es dueño del hilo worker.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from fastapi import Depends

from ..core.secrets import SecretsService
from ..core.settings import AppSettings, SettingsStore
from ..models.db import Database
from ..models.jobs import JobRepository
from ..models.projects import ProjectRepository
from ..services.job_manager import JobManager


@lru_cache(maxsize=1)
def get_settings_store() -> SettingsStore:
    return SettingsStore()


@lru_cache(maxsize=1)
def get_secrets() -> SecretsService:
    return SecretsService()


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database()


def get_settings() -> AppSettings:
    return get_settings_store().resolve()


def get_projects(db: Database = Depends(get_database)) -> ProjectRepository:
    return ProjectRepository(db)


def get_jobs(db: Database = Depends(get_database)) -> JobRepository:
    return JobRepository(db)


# Un manager por base de datos: en producción hay una sola; en los tests, una
# por directorio temporal.
_managers: Dict[str, JobManager] = {}


def get_job_manager(db: Database = Depends(get_database)) -> JobManager:
    key = str(db.path)
    if key not in _managers:
        _managers[key] = JobManager(JobRepository(db), ProjectRepository(db))
    return _managers[key]


def shutdown_job_managers() -> None:
    for manager in list(_managers.values()):
        manager.shutdown()
    _managers.clear()
