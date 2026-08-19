"""Backend de IA para el modo local: OpenAI, Gemini o Groq.

Además de elegir proveedor, este módulo implementa la **red de contención**: si
el proveedor principal se queda sin saldo o te limita los pedidos, prueba con
el siguiente que tengas configurado en vez de tirar abajo el procesamiento
entero. Un video a medio analizar no se recupera; cambiar de proveedor sí.
"""
from ..config import (
    GEMINI_MODEL,
    GROQ_BASE_URL,
    GROQ_MODEL,
    LLM_PROVIDER_ORDER,
    OPENAI_MODEL,
    require_gemini_key,
    require_groq_key,
    require_openai_key,
)

# Fallos que justifican probar con otro proveedor. Un JSON mal formado, en
# cambio, se resuelve reintentando con el mismo: cambiar no ayudaría.
_WORTH_SWITCHING = (
    "insufficient_quota",
    "exceeded your current quota",
    "rate limit",
    "429",
    "quota",
    "401",
    "unauthorized",
    "api key",
    "not found",
    "no longer available",
    "does not exist",
)


def _openai_compatible(prompt: str, api_key: str, model: str, base_url=None) -> str:
    """OpenAI y cualquiera que hable su mismo protocolo, como Groq."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openai is required for --mode local. Install it with:\n"
            "    pip install -r requirements.txt"
        ) from e

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def call_openai_llm(prompt: str) -> str:
    return _openai_compatible(prompt, require_openai_key(), OPENAI_MODEL)


def call_groq_llm(prompt: str) -> str:
    return _openai_compatible(prompt, require_groq_key(), GROQ_MODEL, GROQ_BASE_URL)


def call_gemini_llm(prompt: str) -> str:
    """Gemini pide el JSON por configuración, así que no hace falta rogarlo."""
    try:
        from google import genai  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "google-genai is required for LLM_PROVIDER=gemini. Install it with:\n"
            "    pip install -r requirements.txt"
        ) from e

    client = genai.Client(api_key=require_gemini_key())
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
            "max_output_tokens": 8192,
        },
    )
    return response.text or ""


_BACKENDS = {
    "openai": call_openai_llm,
    "gemini": call_gemini_llm,
    "groq": call_groq_llm,
}


def _worth_switching(exc: Exception) -> bool:
    detail = str(exc).lower()
    return any(marker in detail for marker in _WORTH_SWITCHING)


def call_local_llm(prompt: str) -> str:
    """Llamar al proveedor configurado, cayendo al siguiente si se queda sin nafta."""
    order = [p for p in LLM_PROVIDER_ORDER if p in _BACKENDS] or ["openai"]
    last_error = None

    for position, provider in enumerate(order):
        try:
            return _BACKENDS[provider](prompt)
        except Exception as exc:
            last_error = exc
            hay_otro = position < len(order) - 1
            if not (hay_otro and _worth_switching(exc)):
                raise
            print(
                "[llm] {0} falló ({1}); sigo con {2}".format(
                    provider, str(exc)[:80], order[position + 1]
                ),
                flush=True,
            )

    raise last_error if last_error else RuntimeError("no LLM provider available")
