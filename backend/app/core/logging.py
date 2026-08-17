"""Logging con redacción de credenciales.

Ningún log de Andy Clip debe contener una API key, un header `Authorization`
ni un token. Como el material sensible puede colarse por el mensaje de una
excepción de un SDK, la redacción se aplica en el filtro y no en cada `log.*`.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List, Pattern

REDACTED = "[redacted]"

_PATTERNS: List[Pattern[str]] = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),            # OpenAI
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),          # Google
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+"),  # Authorization: Bearer ...
    re.compile(
        r"(?i)\b(api[_-]?key|authorization|token|secret|password)\b\s*[=:]\s*[\"']?[^\s\"',}]+"
    ),
]


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.msg = record.getMessage()
            record.args = ()
        record.msg = redact(str(record.msg))
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def setup_logging(level: str = "info") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s — %(message)s"))
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


LOG_LEVEL = os.environ.get("ANDY_CLIP_LOG_LEVEL", "info")
