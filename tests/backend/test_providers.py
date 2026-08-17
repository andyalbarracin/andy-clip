"""Proveedores de IA. Todo mockeado: ningún test hace una llamada paga."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core.errors import (
    MissingCredentialError,
    ProviderAuthError,
    ProviderError,
)
from app.services.providers import build_llm_fn, build_provider
from app.services.providers.gemini_provider import GeminiProvider
from app.services.providers.openai_provider import OpenAIProvider

FAKE_KEY = "sk-test-0000000000000000000000004F2A"


# ─────────────────────────────────────────────────────────────────────────────
# Dobles de los SDK
# ─────────────────────────────────────────────────────────────────────────────

class FakeAuthError(Exception):
    status_code = 401


class FakeRateLimitError(Exception):
    status_code = 429


class FakeOpenAIClient:
    def __init__(self, completion=None, models=None, error=None):
        self._error = error
        self._completion = completion
        self._models = models or []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(list=self._list)

    def _create(self, **kwargs):
        if self._error:
            raise self._error
        self.last_request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._completion))]
        )

    def _list(self):
        if self._error:
            raise self._error
        return [SimpleNamespace(id=model_id) for model_id in self._models]


class FakeGeminiClient:
    def __init__(self, text=None, models=None, error=None):
        self._error = error
        self._text = text
        self._models = models or []
        self.models = SimpleNamespace(
            generate_content=self._generate,
            list=self._list,
        )

    def _generate(self, **kwargs):
        if self._error:
            raise self._error
        self.last_request = kwargs
        return SimpleNamespace(text=self._text)

    def _list(self):
        if self._error:
            raise self._error
        return self._models


def _with_client(provider, client):
    provider._client = lambda: client  # type: ignore[method-assign]
    return provider


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────────────────────────────────────

def test_openai_generate_returns_the_message_content():
    provider = _with_client(
        OpenAIProvider(api_key=FAKE_KEY, model="gpt-4o-mini"),
        FakeOpenAIClient(completion="hola"),
    )

    assert provider.generate("prompt") == "hola"


def test_openai_generate_uses_the_configured_model():
    client = FakeOpenAIClient(completion="ok")
    provider = _with_client(OpenAIProvider(api_key=FAKE_KEY, model="gpt-4.1"), client)

    provider.generate("prompt")

    assert client.last_request["model"] == "gpt-4.1"


def test_openai_auth_error_becomes_a_readable_error():
    provider = _with_client(
        OpenAIProvider(api_key=FAKE_KEY, model="gpt-4o-mini"),
        FakeOpenAIClient(error=FakeAuthError("Incorrect API key provided")),
    )

    with pytest.raises(ProviderAuthError) as excinfo:
        provider.generate("prompt")

    assert "OpenAI" in excinfo.value.message
    assert excinfo.value.action == "settings/ai"
    assert FAKE_KEY not in str(excinfo.value.message)


def test_openai_rate_limit_is_not_reported_as_an_auth_problem():
    provider = _with_client(
        OpenAIProvider(api_key=FAKE_KEY, model="gpt-4o-mini"),
        FakeOpenAIClient(error=FakeRateLimitError("rate limit reached")),
    )

    with pytest.raises(ProviderError) as excinfo:
        provider.generate("prompt")

    assert not isinstance(excinfo.value, ProviderAuthError)


def test_openai_list_models_keeps_only_chat_models():
    provider = _with_client(
        OpenAIProvider(api_key=FAKE_KEY, model="gpt-4o-mini"),
        FakeOpenAIClient(
            models=[
                "gpt-4o-mini",
                "gpt-4o",
                "o3-mini",
                "gpt-4o-audio-preview",
                "text-embedding-3-small",
                "dall-e-3",
                "whisper-1",
            ]
        ),
    )

    assert provider.list_models() == ["gpt-4o", "gpt-4o-mini", "o3-mini"]


def test_openai_test_connection_flags_an_unavailable_model():
    provider = _with_client(
        OpenAIProvider(api_key=FAKE_KEY, model="gpt-9000"),
        FakeOpenAIClient(models=["gpt-4o-mini"]),
    )

    result = provider.test_connection()

    assert result.ok is True
    assert "gpt-9000" in result.message


def test_openai_test_connection_reports_a_bad_key():
    provider = _with_client(
        OpenAIProvider(api_key=FAKE_KEY, model="gpt-4o-mini"),
        FakeOpenAIClient(error=FakeAuthError("invalid_api_key")),
    )

    with pytest.raises(ProviderAuthError):
        provider.test_connection()


# ─────────────────────────────────────────────────────────────────────────────
# Gemini
# ─────────────────────────────────────────────────────────────────────────────

def test_gemini_generate_returns_text():
    provider = _with_client(
        GeminiProvider(api_key=FAKE_KEY, model="gemini-2.5-flash"),
        FakeGeminiClient(text='{"ok": true}'),
    )

    assert provider.generate("prompt") == '{"ok": true}'


def test_gemini_list_models_keeps_only_generative_ones():
    provider = _with_client(
        GeminiProvider(api_key=FAKE_KEY, model="gemini-2.5-flash"),
        FakeGeminiClient(
            models=[
                SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/text-embedding-004", supported_actions=["embedContent"]),
                SimpleNamespace(name="models/gemini-2.5-pro"),  # sin acciones informadas
            ]
        ),
    )

    assert provider.list_models() == ["gemini-2.5-flash", "gemini-2.5-pro"]


def test_gemini_auth_error_becomes_a_readable_error():
    provider = _with_client(
        GeminiProvider(api_key=FAKE_KEY, model="gemini-2.5-flash"),
        FakeGeminiClient(error=Exception("API key not valid. Please pass a valid API key.")),
    )

    with pytest.raises(ProviderAuthError) as excinfo:
        provider.generate("prompt")

    assert "Gemini" in excinfo.value.message


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

def test_build_provider_without_a_key_asks_for_configuration(settings_store, secrets_service):
    with pytest.raises(MissingCredentialError):
        build_provider(settings_store.resolve(), secrets_service)


def test_build_provider_honours_the_default_provider(settings_store, secrets_service):
    secrets_service.set("gemini", FAKE_KEY)
    settings_store.update({"ai": {"provider": "gemini", "gemini_model": "gemini-2.5-pro"}})

    provider = build_provider(settings_store.resolve(), secrets_service)

    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-2.5-pro"


def test_build_provider_can_target_a_specific_provider(settings_store, secrets_service):
    secrets_service.set("openai", FAKE_KEY)

    provider = build_provider(settings_store.resolve(), secrets_service, provider="openai")

    assert isinstance(provider, OpenAIProvider)


def test_build_llm_fn_plugs_into_the_original_core(settings_store, secrets_service, monkeypatch):
    """El core sigue recibiendo un `llm_fn(prompt) -> str`, como lo dejó upstream."""
    from app.engine.highlights import get_highlights

    canned = json.dumps(
        {
            "highlights": [
                {
                    "title": "El momento",
                    "start_time": 10.0,
                    "end_time": 70.0,
                    "score": 88,
                    "hook_sentence": "Nadie habla de esto",
                    "virality_reason": "Revelación inesperada",
                }
            ]
        }
    )
    monkeypatch.setattr(OpenAIProvider, "generate", lambda self, prompt: canned)
    secrets_service.set("openai", FAKE_KEY)

    llm_fn = build_llm_fn(settings_store.resolve(), secrets_service)
    result = get_highlights(
        {"duration": 120.0, "segments": [{"start": 0.0, "end": 120.0, "text": "hola"}]},
        num_clips=1,
        llm_fn=llm_fn,
    )

    assert len(result["highlights"]) == 1
    assert result["highlights"][0]["title"] == "El momento"
