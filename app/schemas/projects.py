"""Cuerpos de request de proyectos."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RerenderBody(_Strict):
    """Ajustes del editor. Todo opcional: lo que no venga queda como está."""

    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    framing: Optional[str] = None
    background: Optional[str] = None
    background_color: Optional[str] = None


class HighlightEdit(_Strict):
    """Recorte de un momento: dónde empieza, dónde termina, si se genera."""

    start_time: Optional[float] = Field(default=None, ge=0)
    end_time: Optional[float] = Field(default=None, gt=0)
    selected: Optional[bool] = None


class ProcessingOptionsBody(_Strict):
    """Lo que la persona puede cambiar en el formulario de un proyecto.

    Todo opcional: lo que no venga se toma de la configuración global.
    """

    mode: Optional[str] = None
    num_clips: Optional[int] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    language: Optional[str] = None


class ProjectCreate(_Strict):
    source: str = Field(min_length=1, max_length=2048)
    name: Optional[str] = Field(default=None, max_length=120)
    options: Optional[ProcessingOptionsBody] = None


class ProjectRename(_Strict):
    name: str = Field(min_length=1, max_length=120)
