"""Precedencia y validación de la configuración."""
from __future__ import annotations

import json

import pytest

from app.core.errors import ConfigurationError
from app.core.settings import SettingsStore


def test_defaults_when_nothing_is_configured(settings_store):
    settings = settings_store.resolve()

    assert settings.mode == "local"
    assert settings.ai.provider == "openai"
    assert settings.ai.openai_model == "gpt-4o-mini"
    assert settings.video.aspect_ratio == "9:16"
    assert settings.video.num_clips == 3
    assert settings.video.resolution == "720"
    assert settings.transcription.whisper_model == "base"
    assert settings.transcription.language is None


def test_env_var_overrides_default(settings_store, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("ANDY_CLIP_NUM_CLIPS", "5")
    monkeypatch.setenv("LOCAL_WHISPER_VAD_FILTER", "true")

    settings = settings_store.resolve()

    assert settings.ai.provider == "gemini"
    assert settings.video.num_clips == 5
    assert settings.transcription.vad_filter is True


def test_saved_settings_win_over_env(settings_store, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    settings_store.update({"ai": {"provider": "openai"}})

    assert settings_store.resolve().ai.provider == "openai"


def test_untouched_fields_still_come_from_env(settings_store, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    settings_store.update({"video": {"num_clips": 4}})

    settings = settings_store.resolve()
    assert settings.ai.openai_model == "gpt-4o"  # sigue viniendo del entorno
    assert settings.video.num_clips == 4


def test_sources_reports_where_each_value_came_from(settings_store, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    settings_store.update({"video": {"num_clips": 4}})

    sources = settings_store.sources()
    assert sources["video.num_clips"] == "app"
    assert sources["ai.openai_model"] == "env"
    assert sources["ai.provider"] == "default"


def test_update_merges_instead_of_replacing_the_branch(settings_store):
    settings_store.update({"ai": {"provider": "gemini"}})
    settings_store.update({"ai": {"gemini_model": "gemini-2.5-pro"}})

    settings = settings_store.resolve()
    assert settings.ai.provider == "gemini"
    assert settings.ai.gemini_model == "gemini-2.5-pro"


@pytest.mark.parametrize(
    "patch",
    [
        {"ai": {"provider": "acme"}},
        {"video": {"aspect_ratio": "16:9"}},
        {"video": {"num_clips": 0}},
        {"video": {"num_clips": 99}},
        {"video": {"resolution": "4k"}},
        {"transcription": {"whisper_model": "enormous"}},
        {"transcription": {"device": "tpu"}},
        {"mode": "cloud"},
    ],
)
def test_invalid_values_are_rejected(settings_store, patch):
    with pytest.raises(ConfigurationError):
        settings_store.update(patch)


def test_rejected_update_is_not_persisted(settings_store):
    settings_store.update({"video": {"num_clips": 4}})

    with pytest.raises(ConfigurationError):
        settings_store.update({"video": {"num_clips": 999}})

    assert settings_store.resolve().video.num_clips == 4


def test_output_dir_cannot_escape_the_project(settings_store):
    with pytest.raises(ConfigurationError):
        settings_store.update({"video": {"output_dir": "../../../etc"}})

    with pytest.raises(ConfigurationError):
        settings_store.update({"video": {"output_dir": "/tmp/andy-clip-out"}})


def test_invalid_env_value_raises_a_readable_error(settings_store, monkeypatch):
    monkeypatch.setenv("ANDY_CLIP_NUM_CLIPS", "muchos")

    with pytest.raises(ConfigurationError) as excinfo:
        settings_store.resolve()

    assert "ANDY_CLIP_NUM_CLIPS" in excinfo.value.message


def test_unreadable_settings_file_raises_configuration_error(settings_store):
    settings_store.path.write_text("{no es json", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        settings_store.resolve()


def test_reset_goes_back_to_env_and_defaults(settings_store, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    settings_store.update({"ai": {"provider": "openai"}})

    settings = settings_store.reset()

    assert settings.ai.provider == "gemini"
    assert not settings_store.path.exists()


def test_only_touched_fields_are_written_to_disk(settings_store):
    settings_store.update({"video": {"num_clips": 4}})

    stored = json.loads(settings_store.path.read_text(encoding="utf-8"))
    assert stored == {"video": {"num_clips": 4}}


def test_analysis_settings_mirror_the_core():
    from app.engine import highlights as core_highlights

    from app.core.settings import analysis_settings

    analysis = analysis_settings()
    assert analysis.chunk_size_seconds == core_highlights.CHUNK_SIZE_SECONDS
    assert analysis.long_video_threshold_seconds == core_highlights.LONG_VIDEO_THRESHOLD


# ── encuadre ─────────────────────────────────────────────────────────────────

def test_framing_defaults_to_cropping_on_faces(settings_store):
    video = settings_store.resolve().video

    assert video.framing == "faces"
    assert video.background == "blur"


def test_fitting_the_whole_frame_can_be_chosen(settings_store):
    settings_store.update({"video": {"framing": "fit", "background": "gradient"}})

    video = settings_store.resolve().video
    assert video.framing == "fit"
    assert video.background == "gradient"


@pytest.mark.parametrize(
    "patch",
    [
        {"video": {"framing": "zoom"}},
        {"video": {"background": "arcoiris"}},
        {"video": {"background_color": "rojo"}},
        {"video": {"background_color": "#GGG"}},
        # Un color es texto que termina en un comando de FFmpeg.
        {"video": {"background_color": "#000000; rm -rf /"}},
    ],
)
def test_invalid_framing_values_are_rejected(settings_store, patch):
    with pytest.raises(ConfigurationError):
        settings_store.update(patch)
