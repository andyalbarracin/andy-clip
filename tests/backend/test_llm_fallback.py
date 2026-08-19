"""La red de contención entre proveedores. Sin red: los backends se simulan."""
from __future__ import annotations

import pytest

from app.engine.local import llm


@pytest.fixture
def backends(monkeypatch):
    """Reemplaza los tres proveedores por funciones controladas."""
    llamados = []

    def hacer(nombre, comportamiento):
        def backend(prompt):
            llamados.append(nombre)
            if isinstance(comportamiento, Exception):
                raise comportamiento
            return comportamiento
        return backend

    def configurar(orden, **comportamientos):
        monkeypatch.setattr(
            llm, "_BACKENDS", {k: hacer(k, v) for k, v in comportamientos.items()}
        )
        monkeypatch.setattr(llm, "LLM_PROVIDER_ORDER", orden)
        return llamados

    return configurar


def test_the_first_provider_answers_and_nobody_else_is_called(backends):
    llamados = backends(
        ["gemini", "groq"], gemini="respuesta", groq="no debería llegar acá"
    )

    assert llm.call_local_llm("hola") == "respuesta"
    assert llamados == ["gemini"]


def test_running_out_of_credit_falls_through_to_the_next(backends):
    llamados = backends(
        ["gemini", "groq"],
        gemini=Exception("Error code: 429 insufficient_quota"),
        groq="respuesta del respaldo",
    )

    assert llm.call_local_llm("hola") == "respuesta del respaldo"
    assert llamados == ["gemini", "groq"]


def test_a_rate_limit_also_falls_through(backends):
    llamados = backends(
        ["openai", "groq"],
        openai=Exception("rate limit exceeded"),
        groq="ok",
    )

    assert llm.call_local_llm("hola") == "ok"
    assert llamados == ["openai", "groq"]


def test_an_unrelated_failure_does_not_switch_providers(backends):
    """Cambiar de proveedor no arregla un problema de red: no lo escondemos."""
    llamados = backends(
        ["gemini", "groq"],
        gemini=Exception("connection reset by peer"),
        groq="no debería llegar acá",
    )

    with pytest.raises(Exception, match="connection reset"):
        llm.call_local_llm("hola")

    assert llamados == ["gemini"]


def test_when_everyone_runs_dry_the_last_error_surfaces(backends):
    backends(
        ["gemini", "groq"],
        gemini=Exception("insufficient_quota en gemini"),
        groq=Exception("insufficient_quota en groq"),
    )

    with pytest.raises(Exception, match="groq"):
        llm.call_local_llm("hola")


def test_an_unknown_provider_in_the_order_is_ignored(backends):
    llamados = backends(["inventado", "groq"], groq="ok")

    assert llm.call_local_llm("hola") == "ok"
    assert llamados == ["groq"]
