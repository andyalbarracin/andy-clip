#!/usr/bin/env bash
#
# Doble clic acá y se abre Andy Clip.
#
# Este archivo prende el servidor de Andy Clip y abre el navegador solo.
# Para cerrarlo, cerrá esta ventana negra o apretá Ctrl+C.
#
cd "$(dirname "$0")"

HOST="${ANDY_CLIP_HOST:-127.0.0.1}"
PORT="${ANDY_CLIP_PORT:-8756}"

# Prepara todo y prende el servidor en segundo plano.
./start.sh &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT INT TERM

# Espera a que conteste y recién ahí abre el navegador.
for _ in $(seq 1 120); do
  if curl -sf "http://$HOST:$PORT/api/health" >/dev/null 2>&1; then
    open "http://$HOST:$PORT"
    break
  fi
  sleep 1
done

wait $SERVER
