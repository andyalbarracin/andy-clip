#!/usr/bin/env bash
#
# Andy Clip — un solo comando, una sola dirección.
#
#   ./start.sh          compila la interfaz si hace falta y levanta la app
#   ./start.sh dev      modo desarrollo, con recarga en caliente
#
set -euo pipefail
cd "$(dirname "$0")"

HOST="${ANDY_CLIP_HOST:-127.0.0.1}"
PORT="${ANDY_CLIP_PORT:-8756}"
PYTHON=".venv/bin/python"

say() { printf "\033[38;5;179m▸\033[0m %s\n" "$1"; }
fail() { printf "\033[38;5;167m✗\033[0m %s\n" "$1" >&2; exit 1; }

# ── Entorno de Python ────────────────────────────────────────────────────────
#
# Hace falta 3.10 o superior: yt-dlp dejó de publicar versiones para 3.9, y sin
# yt-dlp al día YouTube deja de descargarse. En macOS `python3` suele seguir
# apuntando al 3.9 del sistema, así que buscamos uno moderno a propósito.
find_python() {
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

if [ ! -x "$PYTHON" ]; then
  INTERPRETER="$(find_python)" || fail "Hace falta Python 3.10 o superior. En macOS: brew install python@3.13"
  say "Creando el entorno con $("$INTERPRETER" --version)"
  "$INTERPRETER" -m venv .venv
  "$PYTHON" -m pip install --upgrade pip --quiet
  "$PYTHON" -m pip install -r requirements.txt --quiet
elif ! "$PYTHON" -c "import fastapi" >/dev/null 2>&1; then
  say "Instalando dependencias de Python"
  "$PYTHON" -m pip install -r requirements.txt --quiet
fi

# Un entorno viejo con 3.9 arrastra un yt-dlp que YouTube ya rechaza.
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  fail "El entorno .venv usa $("$PYTHON" --version), que ya no sirve para descargar de YouTube.
  Borrá la carpeta .venv y volvé a ejecutar este script para recrearla."
fi

# ── FFmpeg ───────────────────────────────────────────────────────────────────
if ! command -v ffmpeg >/dev/null 2>&1; then
  printf "\033[38;5;179m!\033[0m %s\n" \
    "FFmpeg no está instalado. La app abre igual, pero no va a poder generar clips."
  printf "  macOS: brew install ffmpeg   ·   Ubuntu: sudo apt install ffmpeg\n"
fi

# ── Interfaz ─────────────────────────────────────────────────────────────────
if [ ! -d web/node_modules ]; then
  say "Instalando dependencias de la interfaz"
  (cd web && npm install --silent)
fi

if [ "${1:-}" = "dev" ]; then
  say "Modo desarrollo"
  "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload &
  BACKEND=$!
  trap 'kill $BACKEND 2>/dev/null || true' EXIT INT TERM
  (cd web && npm run dev)
  exit 0
fi

if [ ! -f web/dist/index.html ] || [ -n "$(find web/src web/index.html -newer web/dist/index.html 2>/dev/null | head -1)" ]; then
  say "Compilando la interfaz"
  (cd web && npm run build)
fi

say "Andy Clip en http://$HOST:$PORT"
exec "$PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
