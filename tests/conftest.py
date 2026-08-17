"""Fixtures compartidas. Ningún test toca `.local/` real ni llama a una API paga."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Variables de entorno que participan de la precedencia de configuración.
# Se limpian en cada test para que el `.env` de quien corra los tests no cambie
# el resultado.
MANAGED_ENV_VARS = (
    "ANDY_CLIP_MODE",
    "ANDY_CLIP_ASPECT_RATIO",
    "ANDY_CLIP_NUM_CLIPS",
    "ANDY_CLIP_RESOLUTION",
    "LLM_PROVIDER",
    "OPENAI_MODEL",
    "GEMINI_MODEL",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "MUAPI_API_KEY",
    "LOCAL_WHISPER_MODEL",
    "LOCAL_WHISPER_DEVICE",
    "LOCAL_WHISPER_VAD_FILTER",
    "LOCAL_WHISPER_LANGUAGE",
    "LOCAL_OUTPUT_DIR",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in MANAGED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings_store(tmp_path):
    from app.core.settings import SettingsStore

    return SettingsStore(path=tmp_path / "settings.json")


@pytest.fixture
def secrets_service(tmp_path):
    from app.core.secrets import SecretsService

    return SecretsService(path=tmp_path / "secrets.json")


@pytest.fixture
def database(tmp_path, monkeypatch):
    """Base SQLite temporal, también para el `get_database()` del startup."""
    from app.api import deps
    from app.models import db as db_module

    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    deps.get_database.cache_clear()

    instance = db_module.Database()
    instance.initialize()
    yield instance

    deps.shutdown_job_managers()
    deps.get_database.cache_clear()


@pytest.fixture
def projects_repo(database):
    from app.models.projects import ProjectRepository

    return ProjectRepository(database)


@pytest.fixture
def jobs_repo(database):
    from app.models.jobs import JobRepository

    return JobRepository(database)


@pytest.fixture
def job_manager(jobs_repo, projects_repo):
    from app.services.job_manager import JobManager

    manager = JobManager(jobs_repo, projects_repo)
    yield manager
    manager.shutdown()


@pytest.fixture
def client(settings_store, secrets_service, database):
    """Cliente HTTP con configuración, secrets y base apuntando a tmp_path."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_database, get_secrets, get_settings_store
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_settings_store] = lambda: settings_store
    app.dependency_overrides[get_secrets] = lambda: secrets_service
    app.dependency_overrides[get_database] = lambda: database
    # raise_server_exceptions=False para poder verificar el handler de 500.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
