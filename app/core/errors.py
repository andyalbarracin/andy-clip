"""Errores con dos caras: un mensaje para la persona y un detalle técnico.

La UI nunca debe mostrar un `500 Internal Server Error` pelado, así que todo
error previsible viaja como `AppError`: `message` va a la pantalla en es-AR,
`detail` va al log, y `action` le dice al frontend adónde puede mandar al
usuario para resolverlo.
"""
from __future__ import annotations

from typing import Optional


class AppError(Exception):
    """Base de todos los errores esperables de Andy Clip."""

    code = "error"
    status_code = 400

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.action = action


class ConfigurationError(AppError):
    """Falta configuración o la configuración guardada es inválida."""

    code = "configuration_error"
    status_code = 400


class MissingCredentialError(ConfigurationError):
    """El proveedor existe pero no tiene API key cargada."""

    code = "missing_credential"
    status_code = 400

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        super().__init__(message, detail=detail, action="settings/ai")


class ProviderError(AppError):
    """El proveedor de IA respondió con un error."""

    code = "provider_error"
    status_code = 502


class ProviderAuthError(ProviderError):
    """La API key fue rechazada."""

    code = "provider_auth_error"
    status_code = 502

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        super().__init__(message, detail=detail, action="settings/ai")


class PathValidationError(AppError):
    """Un path apunta fuera de los directorios permitidos."""

    code = "invalid_path"
    status_code = 400


class DependencyMissingError(AppError):
    """Falta una dependencia del sistema (FFmpeg) o un paquete opcional."""

    code = "dependency_missing"
    status_code = 400
