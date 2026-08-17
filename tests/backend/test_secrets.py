"""Guardado, masking y no-filtración de API keys."""
from __future__ import annotations

import json
import stat

import pytest

from app.core.errors import ConfigurationError, MissingCredentialError
from app.core.secrets import mask_secret

FAKE_KEY = "sk-test-0000000000000000000000004F2A"


def test_missing_secret_reports_absence(secrets_service):
    assert secrets_service.get("openai") is None
    assert secrets_service.has("openai") is False
    assert secrets_service.masked("openai") is None
    assert secrets_service.source("openai") is None


def test_set_and_read_back(secrets_service):
    secrets_service.set("openai", FAKE_KEY)

    assert secrets_service.get("openai") == FAKE_KEY
    assert secrets_service.has("openai") is True
    assert secrets_service.source("openai") == "app"


def test_env_var_is_used_when_nothing_was_saved(secrets_service, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)

    assert secrets_service.get("gemini") == FAKE_KEY
    assert secrets_service.source("gemini") == "env"


def test_saved_secret_wins_over_env(secrets_service, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-aaaaaaaaaaaaaaaaaaaa")
    secrets_service.set("openai", FAKE_KEY)

    assert secrets_service.get("openai") == FAKE_KEY
    assert secrets_service.source("openai") == "app"


def test_delete_removes_the_saved_secret(secrets_service):
    secrets_service.set("openai", FAKE_KEY)
    secrets_service.delete("openai")

    assert secrets_service.get("openai") is None


def test_delete_is_idempotent(secrets_service):
    secrets_service.delete("muapi")  # no debe explotar


def test_mask_keeps_only_the_edges():
    masked = mask_secret(FAKE_KEY)

    assert masked.startswith("sk-")
    assert masked.endswith("4F2A")
    assert FAKE_KEY not in masked
    assert "0000" not in masked


def test_mask_hides_short_values_completely():
    assert mask_secret("abc123") == "••••••••"


def test_status_never_exposes_the_full_key(secrets_service):
    secrets_service.set("openai", FAKE_KEY)

    status = secrets_service.status()
    serialized = json.dumps(status)

    assert FAKE_KEY not in serialized
    assert status["openai"]["configured"] is True
    assert status["openai"]["masked"].endswith("4F2A")
    assert status["gemini"]["configured"] is False
    assert status["muapi"]["configured"] is False


def test_secrets_file_is_not_world_readable(secrets_service):
    secrets_service.set("openai", FAKE_KEY)

    mode = stat.S_IMODE(secrets_service.path.stat().st_mode)
    assert mode & (stat.S_IRWXG | stat.S_IRWXO) == 0


def test_require_raises_a_pointed_error(secrets_service):
    with pytest.raises(MissingCredentialError) as excinfo:
        secrets_service.require("openai")

    assert "OpenAI" in excinfo.value.message
    assert excinfo.value.action == "settings/ai"


@pytest.mark.parametrize("value", ["", "   ", "clave\ncon\nsaltos", "x" * 501])
def test_invalid_keys_are_rejected(secrets_service, value):
    with pytest.raises(ConfigurationError):
        secrets_service.set("openai", value)


def test_unknown_provider_is_rejected(secrets_service):
    with pytest.raises(ConfigurationError):
        secrets_service.set("acme", FAKE_KEY)


def test_corrupt_secrets_file_does_not_leak_content(secrets_service):
    secrets_service.path.write_text('{"openai": "sk-leaked', encoding="utf-8")

    with pytest.raises(ConfigurationError) as excinfo:
        secrets_service.get("openai")

    assert "sk-leaked" not in str(excinfo.value.detail or "")
