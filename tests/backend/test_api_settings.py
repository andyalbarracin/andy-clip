"""API de configuración. Los proveedores están mockeados en todos los casos."""
from __future__ import annotations

import json

import pytest

from backend.app.core.errors import ProviderAuthError
from backend.app.services.providers.base import ProviderTestResult

FAKE_KEY = "sk-test-0000000000000000000000004F2A"


class FakeProvider:
    name = "openai"
    label = "OpenAI"
    model = "gpt-4o-mini"

    def generate(self, prompt):  # pragma: no cover - no se usa acá
        return ""

    def test_connection(self):
        return ProviderTestResult(ok=True, message="Conectamos con OpenAI.", models=["gpt-4o-mini"])

    def list_models(self):
        return ["gpt-4o-mini", "gpt-4o"]


@pytest.fixture
def fake_provider(monkeypatch):
    from backend.app.api.routes import settings as settings_routes

    monkeypatch.setattr(settings_routes, "build_provider", lambda *a, **k: FakeProvider())
    return FakeProvider()


# ── health / sistema ─────────────────────────────────────────────────────────

def test_health_works_without_any_api_key(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Andy Clip"
    assert body["mode"] == "local"
    assert body["local_mode"]["ready"] is False
    assert "un proveedor de IA" in body["local_mode"]["missing"]


def test_system_status_lists_components_without_calling_providers(client):
    response = client.get("/api/system/status")

    assert response.status_code == 200
    ids = {component["id"] for component in response.json()["components"]}
    assert {"python", "ffmpeg", "openai", "gemini", "muapi", "faster_whisper"} <= ids


def test_system_status_reports_unconfigured_providers(client):
    components = {c["id"]: c for c in client.get("/api/system/status").json()["components"]}

    assert components["openai"]["status"] == "not_configured"
    assert components["python"]["status"] == "available"


# ── configuración general ────────────────────────────────────────────────────

def test_read_settings_returns_values_sources_and_options(client):
    body = client.get("/api/settings").json()

    assert body["settings"]["video"]["num_clips"] == 3
    assert body["sources"]["video.num_clips"] == "default"
    assert "9:16" in body["options"]["aspect_ratios"]
    assert body["options"]["max_clips"] == 10


def test_patch_settings_persists_the_change(client):
    response = client.patch("/api/settings", json={"video": {"num_clips": 5}})

    assert response.status_code == 200
    assert response.json()["settings"]["video"]["num_clips"] == 5
    assert client.get("/api/settings").json()["sources"]["video.num_clips"] == "app"


def test_patch_settings_rejects_invalid_values_with_a_readable_message(client):
    response = client.patch("/api/settings", json={"video": {"aspect_ratio": "16:9"}})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "configuration_error"
    assert "16:9" in error["message"]
    assert "Traceback" not in json.dumps(error)


def test_patch_settings_rejects_unknown_fields(client):
    response = client.patch("/api/settings", json={"video": {"bitrate": 9000}})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_patch_settings_rejects_an_empty_body(client):
    assert client.patch("/api/settings", json={}).status_code == 400


def test_output_dir_traversal_is_rejected_over_http(client):
    response = client.patch("/api/settings", json={"video": {"output_dir": "../../etc"}})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "configuration_error"


def test_reset_returns_to_defaults(client):
    client.patch("/api/settings", json={"video": {"num_clips": 7}})

    response = client.post("/api/settings/reset")

    assert response.json()["settings"]["video"]["num_clips"] == 3


# ── proveedores de IA ────────────────────────────────────────────────────────

def test_ai_settings_start_unconfigured(client):
    body = client.get("/api/settings/ai").json()

    providers = {p["id"]: p for p in body["providers"]}
    assert body["default_provider"] == "openai"
    assert providers["openai"]["configured"] is False
    assert providers["openai"]["masked_key"] is None
    assert providers["openai"]["suggested_models"]
    assert providers["muapi"]["testable"] is False


def test_saving_a_key_never_returns_it(client):
    response = client.put("/api/settings/ai/openai/key", json={"api_key": FAKE_KEY})

    assert response.status_code == 200
    assert FAKE_KEY not in response.text
    providers = {p["id"]: p for p in response.json()["providers"]}
    assert providers["openai"]["configured"] is True
    assert providers["openai"]["masked_key"].endswith("4F2A")
    assert providers["openai"]["key_source"] == "app"


def test_the_key_is_never_exposed_by_any_settings_endpoint(client):
    client.put("/api/settings/ai/openai/key", json={"api_key": FAKE_KEY})

    for path in ("/api/settings", "/api/settings/ai", "/api/system/status", "/api/health"):
        assert FAKE_KEY not in client.get(path).text


def test_deleting_a_key_clears_it(client):
    client.put("/api/settings/ai/openai/key", json={"api_key": FAKE_KEY})

    response = client.delete("/api/settings/ai/openai/key")

    providers = {p["id"]: p for p in response.json()["providers"]}
    assert providers["openai"]["configured"] is False


def test_empty_key_is_rejected_without_echoing_the_input(client):
    response = client.put("/api/settings/ai/openai/key", json={"api_key": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_validation_errors_never_echo_the_submitted_value(client):
    response = client.put("/api/settings/ai/openai/key", json={"api_key": 12345, "extra": FAKE_KEY})

    assert response.status_code == 422
    assert FAKE_KEY not in response.text


def test_unknown_provider_is_rejected(client):
    response = client.put("/api/settings/ai/anthropic/key", json={"api_key": FAKE_KEY})

    assert response.status_code == 400


# ── probar conexión / actualizar modelos ─────────────────────────────────────

def test_test_connection_without_a_key_points_at_configuration(client):
    response = client.post("/api/settings/ai/openai/test")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "missing_credential"
    assert error["action"] == "settings/ai"


def test_test_connection_reports_success(client, fake_provider):
    client.put("/api/settings/ai/openai/key", json={"api_key": FAKE_KEY})

    response = client.post("/api/settings/ai/openai/test")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_test_connection_translates_a_rejected_key(client, monkeypatch):
    from backend.app.api.routes import settings as settings_routes

    def explode(*args, **kwargs):
        raise ProviderAuthError("OpenAI rechazó la API key configurada.")

    monkeypatch.setattr(settings_routes, "build_provider", explode)
    client.put("/api/settings/ai/openai/key", json={"api_key": FAKE_KEY})

    response = client.post("/api/settings/ai/openai/test")

    assert response.status_code == 502
    assert response.json()["error"]["action"] == "settings/ai"


def test_refresh_models_returns_the_provider_list(client, fake_provider):
    client.put("/api/settings/ai/openai/key", json={"api_key": FAKE_KEY})

    response = client.post("/api/settings/ai/openai/models")

    assert response.json()["models"] == ["gpt-4o-mini", "gpt-4o"]


def test_muapi_cannot_be_tested_yet(client):
    client.put("/api/settings/ai/muapi/key", json={"api_key": FAKE_KEY})

    response = client.post("/api/settings/ai/muapi/test")

    assert response.status_code == 400
    assert "MuAPI" in response.json()["error"]["message"]
