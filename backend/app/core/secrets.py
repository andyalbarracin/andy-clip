"""Guarda y expone las API keys sin filtrarlas.

Reglas que sostiene este módulo:

* la key completa nunca sale del backend — al frontend solo va la versión
  masked y un booleano de presencia;
* `.local/secrets.json` se escribe con permisos `0600` dentro de `.local/`
  (`0700`), ambos gitignored;
* si la key no está guardada en la app, se cae a la variable de entorno, así
  el `.env` de siempre sigue funcionando.

La abstracción existe para poder migrar más adelante a Keychain (macOS),
Credential Manager (Windows) o Secret Service (Linux) sin tocar el resto de la
aplicación. En V1 el backend **no** accede al keychain del sistema.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from .errors import ConfigurationError
from .paths import LOCAL_DIR

SECRETS_FILENAME = "secrets.json"

SECRET_PROVIDERS: Tuple[str, ...] = ("openai", "gemini", "muapi")

ENV_VARS: Dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "muapi": "MUAPI_API_KEY",
}

MASK_CHAR = "•"
VISIBLE_PREFIX = 3
VISIBLE_SUFFIX = 4


def mask_secret(value: str) -> str:
    """`sk-proj-abc...4F2A` → `sk-•••••••••••••4F2A`.

    Con keys muy cortas no mostramos nada: preferimos un mask inútil antes que
    filtrar la mitad de una credencial.
    """
    value = (value or "").strip()
    if len(value) <= VISIBLE_PREFIX + VISIBLE_SUFFIX:
        return MASK_CHAR * 8
    hidden = max(4, len(value) - VISIBLE_PREFIX - VISIBLE_SUFFIX)
    return value[:VISIBLE_PREFIX] + (MASK_CHAR * min(hidden, 13)) + value[-VISIBLE_SUFFIX:]


class SecretsService:
    """Acceso único a las credenciales de proveedores."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else (LOCAL_DIR / SECRETS_FILENAME)

    # ── lectura ──────────────────────────────────────────────────────────────

    def get(self, provider: str) -> Optional[str]:
        """La key completa. **Solo para uso del backend**, nunca en una response."""
        provider = self._check_provider(provider)
        stored = self._read().get(provider)
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
        env_value = os.environ.get(ENV_VARS[provider], "").strip()
        return env_value or None

    def source(self, provider: str) -> Optional[str]:
        """`"app"`, `"env"` o `None` si no hay key en ningún lado."""
        provider = self._check_provider(provider)
        stored = self._read().get(provider)
        if isinstance(stored, str) and stored.strip():
            return "app"
        if os.environ.get(ENV_VARS[provider], "").strip():
            return "env"
        return None

    def has(self, provider: str) -> bool:
        return self.get(provider) is not None

    def masked(self, provider: str) -> Optional[str]:
        value = self.get(provider)
        return mask_secret(value) if value else None

    def status(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Resumen seguro para el frontend: presencia, mask y origen."""
        result: Dict[str, Dict[str, Optional[str]]] = {}
        for provider in SECRET_PROVIDERS:
            value = self.get(provider)
            result[provider] = {
                "configured": bool(value),
                "masked": mask_secret(value) if value else None,
                "source": self.source(provider),
                "env_var": ENV_VARS[provider],
            }
        return result

    def require(self, provider: str) -> str:
        from .errors import MissingCredentialError

        value = self.get(provider)
        if not value:
            raise MissingCredentialError(
                "Todavía no configuraste la API key de {0}.".format(_label(provider)),
                detail="missing credential for provider={0}".format(provider),
            )
        return value

    # ── escritura ────────────────────────────────────────────────────────────

    def set(self, provider: str, value: str) -> None:
        provider = self._check_provider(provider)
        value = (value or "").strip()
        if not value:
            raise ConfigurationError("La API key no puede quedar vacía.")
        if len(value) > 500 or any(ch in value for ch in "\n\r\t"):
            raise ConfigurationError("Esa API key no tiene un formato válido.")
        secrets = self._read()
        secrets[provider] = value
        self._write(secrets)

    def delete(self, provider: str) -> None:
        provider = self._check_provider(provider)
        secrets = self._read()
        if provider in secrets:
            del secrets[provider]
            self._write(secrets)

    # ── internos ─────────────────────────────────────────────────────────────

    @staticmethod
    def _check_provider(provider: str) -> str:
        provider = (provider or "").strip().lower()
        if provider not in SECRET_PROVIDERS:
            raise ConfigurationError(
                "Proveedor desconocido: {0!r}.".format(provider),
                detail="known providers: {0}".format(", ".join(SECRET_PROVIDERS)),
            )
        return provider

    def _read(self) -> Dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # No incluimos el contenido del archivo en el detalle: puede tener keys.
            raise ConfigurationError(
                "No pudimos leer las credenciales guardadas.",
                detail="unreadable secrets file at {0}: {1}".format(
                    self.path, type(exc).__name__
                ),
            ) from exc
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(v, str)}

    def _write(self, secrets: Dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass

        tmp_path = self.path.with_suffix(".json.tmp")
        # Crear el temporal ya restringido: nunca existe con permisos abiertos.
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(secrets, handle, indent=2, sort_keys=True)
                handle.write("\n")
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        os.replace(str(tmp_path), str(self.path))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass


def _label(provider: str) -> str:
    from .settings import PROVIDER_LABELS

    return PROVIDER_LABELS.get(provider, provider)
