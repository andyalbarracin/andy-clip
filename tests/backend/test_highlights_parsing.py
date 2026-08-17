"""Robustez frente a lo que devuelve el LLM.

Estos tests apuntan al core tal como está (no lo modifican): documentan qué
tolera hoy `app.engine.highlights`, que es de lo que va a depender la UI.
"""
from __future__ import annotations

import json

import pytest

from app.engine.highlights import (
    _parse_json_loose,
    _sanitize_highlights,
    call_highlight_api,
    dedupe_highlights,
)

CONTENT_INFO = {"content_type": "podcast", "density": "high"}


def _highlight(**overrides):
    base = {
        "title": "Momento",
        "start_time": 10.0,
        "end_time": 70.0,
        "score": 80,
        "hook_sentence": "Hook",
        "virality_reason": "Motivo",
    }
    base.update(overrides)
    return base


def test_plain_json_is_parsed():
    assert _parse_json_loose('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json_is_parsed():
    raw = '```json\n{"highlights": []}\n```'
    assert _parse_json_loose(raw) == {"highlights": []}


def test_json_surrounded_by_commentary_is_recovered():
    raw = 'Acá va tu respuesta:\n{"highlights": []}\nEspero que sirva.'
    assert _parse_json_loose(raw) == {"highlights": []}


def test_invalid_timestamps_are_dropped():
    highlights = _sanitize_highlights(
        [
            _highlight(start_time=-5, end_time=20),
            _highlight(start_time=50, end_time=50),
            _highlight(start_time=80, end_time=30),
            _highlight(start_time=10, end_time=70),
        ],
        duration=120.0,
    )

    assert len(highlights) == 1
    assert highlights[0]["start_time"] == 10.0


def test_timestamps_are_clamped_to_the_video_duration():
    highlights = _sanitize_highlights([_highlight(start_time=10, end_time=9999)], duration=120.0)

    assert highlights[0]["end_time"] == 120.0


def test_scores_are_clamped_to_zero_hundred():
    highlights = _sanitize_highlights(
        [_highlight(score=999), _highlight(start_time=200, end_time=260, score=-4)],
        duration=0,
    )

    assert highlights[0]["score"] == 100
    assert highlights[1]["score"] == 0


def test_missing_fields_get_safe_defaults():
    highlights = _sanitize_highlights([{"start_time": 1, "end_time": 30}], duration=60.0)

    assert highlights[0]["title"] == "Untitled Highlight"
    assert highlights[0]["score"] == 0
    assert highlights[0]["hook_sentence"] == ""


def test_non_list_payload_is_ignored():
    assert _sanitize_highlights({"highlights": []}, duration=60.0) == []
    assert _sanitize_highlights(None, duration=60.0) == []


def test_overlapping_highlights_keep_the_higher_score():
    kept = dedupe_highlights(
        [
            _highlight(title="baja", start_time=10, end_time=70, score=40),
            _highlight(title="alta", start_time=15, end_time=75, score=90),
        ]
    )

    assert [h["title"] for h in kept] == ["alta"]


def test_the_llm_is_retried_when_it_returns_garbage():
    responses = ["no soy json", json.dumps({"highlights": [_highlight()]})]
    calls = []

    def llm_fn(prompt):
        calls.append(prompt)
        return responses[len(calls) - 1]

    result = call_highlight_api("transcripción", CONTENT_INFO, 120.0, num_clips=1, llm_fn=llm_fn)

    assert len(calls) == 2
    assert len(result["highlights"]) == 1


def test_retries_are_bounded():
    calls = []

    def llm_fn(prompt):
        calls.append(prompt)
        return "sigue sin ser json"

    with pytest.raises(RuntimeError):
        call_highlight_api("transcripción", CONTENT_INFO, 120.0, num_clips=1, llm_fn=llm_fn)

    assert len(calls) == 3  # MAX_HIGHLIGHT_API_ATTEMPTS
