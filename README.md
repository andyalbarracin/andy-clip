# Andy Clip

Convertí videos largos en clips verticales listos para Shorts, Reels y TikTok.

Andy Clip transcribe el video en tu equipo, le pide a un modelo de IA que
encuentre los mejores momentos, y recorta cada uno en vertical siguiendo las
caras del plano. Todo corre local: el video no sale de tu computadora.

```
VIDEO LARGO → TRANSCRIPCIÓN → ANÁLISIS → MEJORES MOMENTOS → RECORTE → CLIPS 9:16
```

## Empezar

Necesitás Python 3.9 o superior, Node 18 o superior, y FFmpeg.

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

Después, un solo comando:

```bash
./start.sh
```

Prepara el entorno, compila la interfaz y abre Andy Clip en
**http://127.0.0.1:8756**.

La primera vez entrá a **Configuración** y cargá una API key de OpenAI o de
Google Gemini. Es lo único que Andy Clip necesita de afuera: el modelo lee la
transcripción en texto y devuelve los momentos que valen la pena.

## Cómo funciona

| Etapa | Dónde ocurre |
|---|---|
| Descarga del video | Tu equipo (yt-dlp) |
| Transcripción | Tu equipo (faster-whisper) |
| Detección de momentos | El proveedor de IA que configures |
| Recorte y reencuadre | Tu equipo (FFmpeg + OpenCV) |

Lo único que viaja a un servidor externo es el **texto** de la transcripción.
El video, los clips y la base de datos se quedan en tu disco.

## Estructura

```
andy-clip/
├── app/              backend Python
│   ├── engine/       el motor: descarga, transcripción, análisis, recorte
│   ├── api/          rutas HTTP
│   ├── core/         configuración, credenciales, errores, rutas
│   ├── models/       persistencia en SQLite
│   ├── services/     jobs, proveedores de IA, diagnóstico
│   └── cli.py        línea de comandos
├── web/              interfaz (React + TypeScript + Vite)
├── tests/            tests del backend
├── .docs/            documentación del proyecto
├── data/             base SQLite
├── output/           clips generados
└── start.sh
```

## Desarrollo

```bash
./start.sh dev     # backend y frontend con recarga en caliente
```

```bash
.venv/bin/python -m pytest        # tests del backend
cd web && npm test                # tests de la interfaz
```

## Línea de comandos

El motor también se usa sin interfaz:

```bash
.venv/bin/python -m app.cli "https://www.youtube.com/watch?v=..." \
    --mode local --num-clips 3 --aspect-ratio 9:16
```

## Configuración por variables de entorno

Todo se puede configurar desde la aplicación, pero también acepta variables de
entorno. Copiá `.env.example` a `.env` y ajustá lo que necesites. La precedencia
es: configuración guardada en la app → variables de entorno → valores por
defecto.

## Privacidad

Andy Clip no tiene cuentas, ni telemetría, ni analytics. No manda nada a ningún
lado salvo las llamadas al proveedor de IA que vos configures. Las API keys se
guardan en `.local/secrets.json`, fuera del control de versiones y con permisos
restringidos.
