# Baseline del upstream — estado del código antes de Andy Clip

Documento de auditoría. Describe **el código tal como estaba** en el commit baseline,
no lo que dice el README. Sirve como referencia para no romper compatibilidad.

- **Upstream:** https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator
- **Commit baseline:** `c30376e94326f8674793c960b482eb532ffbf1f6` — *"Add demo video embed to README"* (2026-07-29)
- **Auditado el:** 2026-08-17

---

## 1. Arquitectura actual

Un único paquete Python (`shorts_generator/`) con dos implementaciones intercambiables
del mismo pipeline de 4 pasos, más un CLI encima.

```
main.py  (CLI, argparse)
   │
   └── shorts_generator.generate_shorts(...)          pipeline.py
             │
             ├── mode="api"   → _run_api()            todo vía MuAPI
             │     downloader.download_youtube        MuAPI /youtube-download
             │     transcriber.transcribe             MuAPI /openai-whisper
             │     highlights.get_highlights(llm_fn=call_muapi_llm)
             │     clipper.crop_highlights            MuAPI /autocrop
             │
             └── mode="local" → _run_local()          todo en el equipo, salvo el LLM
                   local/downloader.download_youtube_local   yt-dlp / path directo
                   local/transcriber.transcribe_local        faster-whisper
                   highlights.get_highlights(llm_fn=call_local_llm)  OpenAI | Gemini
                   local/clipper.crop_highlights_local       ffmpeg + OpenCV
```

`highlights.py` es **compartido** por los dos modos: contiene los prompts, el chunking
y el dedupe. El backend LLM se inyecta con el parámetro `llm_fn` — este es el punto de
extensión más importante del repo y el que usa Andy Clip.

## 2. Entry points

| Entry point | Firma / uso |
|---|---|
| CLI | `python main.py <url> [--mode api\|local] [--num-clips N] [--aspect-ratio R] [--format 720] [--language xx] [--output-json path]` |
| Python API | `from shorts_generator import generate_shorts` → `generate_shorts(youtube_url, num_clips=3, aspect_ratio="9:16", download_format="720", language=None, mode="api")` |

`main.py` reconfigura `stdout`/`stderr` a UTF-8 (fix Windows/charmap) antes de importar el paquete.

**El default del CLI es `--mode api` (MuAPI).** Andy Clip cambia el default *de la app* a
local, sin tocar el default del CLI.

## 3. Flujo del pipeline (modo local, el que usa Andy Clip)

1. **`download_youtube_local(video_url, fmt, out_dir=LOCAL_OUTPUT_DIR)`**
   - `_resolve_local_path()` primero: si la entrada es `file://` o una ruta existente, la devuelve tal cual (sin copiar, sin descargar).
   - Si es `http(s)`, usa `yt_dlp` con selector `bestvideo[height<=H][ext=mp4]+bestaudio[ext=m4a]/best[height<=H][ext=mp4]/best`, `merge_output_format=mp4`, plantilla `source_%(id)s.%(ext)s`.
   - **Cache:** si existe `out_dir/source_<youtube_id>.{mp4,mkv,webm}` se reusa y se saltea yt-dlp.
   - Requiere `ffmpeg` cuando yt-dlp tiene que mergear video+audio.
2. **`transcribe_local(media_path, language)`**
   - **Cache:** `LOCAL_OUTPUT_DIR/<stem del archivo>.srt`. Se reusa si su `mtime >= mtime` del source. Un cache vacío o con `duration <= 0` se borra y se re-transcribe (fix del commit `1e06eed`).
   - `faster_whisper.WhisperModel(LOCAL_WHISPER_MODEL, device, compute_type)`, `compute_type = float16` en CUDA / `int8` en CPU.
   - `beam_size=5`, `condition_on_previous_text=False`. **VAD desactivado por default** (`LOCAL_WHISPER_VAD_FILTER=false`) porque era demasiado agresivo con contenido mixto voz/música.
   - `_resolve_device()`: con `auto` intenta `torch.cuda.is_available()` **y** una allocation real en CUDA para detectar cuBLAS/cuDNN faltantes; cualquier fallo cae a `cpu`. `torch` no es dependencia obligatoria.
   - Devuelve `{"duration": float, "segments": [{"start","end","text"}]}`.
3. **`get_highlights(transcript, num_clips, llm_fn)`** (compartido)
   - `detect_content_type()` → 1 llamada LLM que clasifica `content_type` + `density`. **Atrapa toda excepción** y cae a `{"other","medium"}`.
   - Si `duration >= LONG_VIDEO_THRESHOLD` (1800s) → `chunk_transcript()` en ventanas de `CHUNK_SIZE_SECONDS` (1200s) con `CHUNK_OVERLAP_SECONDS` (60s) de solape; los `start_time`/`end_time` de cada chunk se re-offsetean al timeline global.
   - `call_highlight_api()` pide `min(max(num_clips*2, 5), max(3, duration/90), 8)` highlights, con hasta `MAX_HIGHLIGHT_API_ATTEMPTS = 3` intentos; en el retry agrega una instrucción extra de "solo JSON".
   - `_parse_json_loose()` tolera fences ```` ```json ```` y busca el primer `{` … último `}`.
   - `_sanitize_highlights()` descarta entradas sin `start_time`/`end_time` válidos (`start >= 0`, `end > start`), clampea a `duration`, clampea `score` a 0–100 y normaliza strings.
   - `dedupe_highlights()` ordena por score desc y descarta un highlight si solapa > 50 % de su propia duración con uno ya aceptado.
   - Devuelve `{"highlights": [...]}` — **todos** los candidatos que sobrevivieron al dedupe.
4. **Top-N + `crop_highlights_local(source_path, top, aspect_ratio, out_dir)`**
   - `pipeline._run_local` ordena por score desc y corta a `num_clips`.
   - Por cada highlight: `_cut_subclip()` (ffmpeg, re-encode libx264 crf 20 + aac 128k) → `_reframe_vertical()` (OpenCV) → mux del audio.
   - `_reframe_vertical` calcula el crop más grande que entra en el frame con el ratio pedido, detecta caras con Haar cascade `haarcascade_frontalface_default.xml`, toma la cara más grande, y suaviza el centro con factor `0.15`. Sin cara → centro del frame.
   - Escribe `out_dir/short_01.mp4`, `short_02.mp4`, … Un clip que falla no aborta el lote: queda `{"clip_url": None, "error": "..."}`.

**Resultado de `generate_shorts`:**
```python
{"mode", "source_video_url", "transcript", "highlights", "shorts"}
```
`highlights` son todos los candidatos; `shorts` son los top-N con `clip_url` (ruta local en modo local, URL hosteada en modo api).

## 4. Configuración

`shorts_generator/config.py` llama `load_dotenv()` y lee **todo a nivel de módulo**:

| Variable | Default en código | Notas |
|---|---|---|
| `MUAPI_API_KEY` | `""` | `require_api_key()` levanta si falta |
| `MUAPI_BASE_URL` | `https://api.muapi.ai/api/v1` | |
| `MUAPI_POLL_INTERVAL` | `5` | |
| `MUAPI_POLL_TIMEOUT` | `600` | ⚠️ el README dice 1800 |
| `LLM_PROVIDER` | `openai` | `openai` \| `gemini` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | `""` / `gpt-4o-mini` | |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | `""` / `gemini-2.5-flash` | |
| `LOCAL_WHISPER_MODEL` | `base` | |
| `LOCAL_WHISPER_DEVICE` | `auto` | `auto` \| `cpu` \| `cuda` |
| `LOCAL_WHISPER_VAD_FILTER` | `false` | |
| `LOCAL_WHISPER_VAD_PARAMETERS` | dict con los defaults de faster-whisper | JSON en env |
| `LOCAL_OUTPUT_DIR` | `output` | relativo al cwd |

Constantes no configurables por env (hay que editar `highlights.py`):
`CHUNK_SIZE_SECONDS=1200`, `LONG_VIDEO_THRESHOLD=1800`, `CHUNK_OVERLAP_SECONDS=60`,
`GPT_CALL_TIMEOUT_SECONDS=300`, `MAX_HIGHLIGHT_API_ATTEMPTS=3`, `VIRALITY_CRITERIA`,
`HIGHLIGHT_SYSTEM_PROMPT`, smoothing del crop (`0.15`), y los flags de ffmpeg.

> **Consecuencia crítica para la app.** La configuración se lee **una sola vez, al importar**,
> y `local/llm.py` y `local/transcriber.py` importan las constantes **por valor**
> (`from ..config import OPENAI_MODEL`). Cambiar `os.environ` o parchear `config` en runtime
> **no** tiene efecto sobre esos módulos. Por eso Andy Clip ejecuta cada job en un
> **proceso hijo** con el entorno ya resuelto antes de importar el core.

## 5. Providers (LLM)

`local/llm.py` — no hay clases ni abstracción; tres funciones y un dispatch por string.

| Provider | Llamada | Parámetros |
|---|---|---|
| OpenAI | `OpenAI(api_key).chat.completions.create()` | `model=OPENAI_MODEL`, `temperature=0.7`, un solo mensaje `user` |
| Gemini | `genai.Client(api_key).models.generate_content()` | `model=GEMINI_MODEL`, `temperature=0.2`, `response_mime_type="application/json"`, `max_output_tokens=8192` |
| MuAPI | `muapi.run("gpt-5-mini", {"prompt": ...})` | timeout 300s; extrae el texto probando `outputs[0]`, `output`, `text`, `response`, `result`, `content` |

Los SDKs se importan **lazy** dentro de cada función, con un `RuntimeError` explicativo si falta el paquete. La asimetría de `temperature` (0.7 vs 0.2) y de `response_mime_type` es del upstream y se preserva.

## 6. Transcripción

Dos backends con la misma forma de salida:
- **api:** MuAPI `/openai-whisper` con `response_format=verbose_json`. `_extract_verbose_payload()` busca el blob con `segments` en `output` / `result` / `outputs`, tolerando dict, lista o string JSON.
- **local:** `faster-whisper` en CPU (int8) o CUDA (float16), con cache `.srt`.

Ninguno de los dos devuelve timestamps por palabra — solo por segmento.

## 7. Downloader

- **api:** MuAPI `/youtube-download`; devuelve una URL hosteada. `_extract_video_url()` prueba `video_url`, `url`, `output_url`, `result_url` y dentro de `outputs`/`output`/`result`.
- **local:** `yt-dlp` para `http(s)`; rutas locales y `file://` pasan derecho. `_extract_youtube_video_id()` soporta `youtu.be/<id>`, `/watch?v=`, `/shorts/`, `/embed/`, `/live/` (solo para la cache).

## 8. Cropper

- **api:** MuAPI `/autocrop` con `start_time`/`end_time`/`aspect_ratio`.
- **local:** ffmpeg + OpenCV Haar cascade (ver §3.4). No usa modelos externos ni descarga pesos.

## 9. Outputs

Todo va a `LOCAL_OUTPUT_DIR` (default `./output`, relativo al cwd), sin subcarpetas:

```
output/
  source_<youtube_id>.mp4    descarga cacheada
  <stem>.srt                 transcripción cacheada
  short_01.mp4 … short_NN.mp4  clips finales
```

## 10. Dependencias

`requirements.txt` (modo api): `requests>=2.31`, `python-dotenv>=1.0`.
`requirements-local.txt`: lo anterior + `yt-dlp`, `faster-whisper`, `openai`, `google-genai`, `opencv-python`. `torch` está comentado (solo para CUDA).
Sistema: **`ffmpeg` en el PATH** para modo local (cut, mux y merge de yt-dlp).

Verificado en este equipo (Python 3.9.6, macOS arm64): instala y importa todo correctamente —
`faster-whisper 1.2.1`, `ctranslate2 4.8.1`, `opencv-python 5.0.0`, `openai 2.48.0`,
`google-genai 1.47.0`, `yt-dlp 2025.10.14`, `numpy 2.0.2`, `av 15.1.0`.

## 11. Diferencias entre README/SKILL y el código real

| # | README / SKILL.md dice | El código hace |
|---|---|---|
| 1 | `MUAPI_POLL_TIMEOUT` default **1800s** | `config.py:11` usa **600s** |
| 2 | Prerequisito **Python 3.10+** | No hay sintaxis 3.10+; corre y se instala bien en **3.9.6** |
| 3 | `git clone .../SamurAIGPT/AI-Youtube-Shorts-Generator.git` | El upstream real de este proyecto es `Anil-matcha/...` (referencia histórica, se ignora) |
| 4 | SKILL.md §8: el crop "auto-handles face tracking and screen recordings; **no Haar cascades**" | El modo local **sí** usa `haarcascade_frontalface_default.xml`. La frase solo aplica al `/autocrop` de MuAPI |
| 5 | SKILL.md §Prerequisites: "A MuAPI key … If missing, **stop**" | El modo local no necesita MuAPI en absoluto |
| 6 | README "Whisper transcription": describe solo el endpoint de MuAPI | En modo local la transcripción es 100 % `faster-whisper` en el equipo |
| 7 | Project Structure omite `shorts_generator/local/__init__.py` | Existe (paquete real) |
| 8 | "Duration sweet spot 45–90s" (prompt) vs SKILL.md "Aim for 30–75s" | El prompt real dice **45–90s**, con 20–44s y 91–180s como excepciones |
| 9 | Tabla: modo local "runs offline **except the LLM call**" | Correcto, pero conviene precisar: se envía **el texto de la transcripción completa** al proveedor de IA |

## 12. Problemas encontrados en el upstream

Ordenados por impacto sobre la app.

| # | Problema | Dónde | Impacto | Qué hace Andy Clip |
|---|---|---|---|---|
| 1 | **Los clips finales quedan en códec MPEG-4 Part 2 (`mp4v`).** OpenCV escribe el reframe con `VideoWriter_fourcc(*"mp4v")` y el mux usa `-c:v copy`, así que el códec sobrevive al MP4 final. Chrome/Edge **no reproducen** ese códec. | `local/clipper.py:72,113` | Bloquea el preview en el navegador y la compatibilidad con redes sociales | Parche mínimo: el mux re-encodea a H.264 (`libx264`, `yuv420p`, `+faststart`) |
| 2 | **`-ss`/`-to` van después de `-i`** en el cut, así que ffmpeg decodifica desde el segundo 0 para *cada* clip. En un video de 2h, sacar 3 clips del final decodifica ~6h de video. | `local/clipper.py:27-35` | Lentitud severa en videos largos | Parche mínimo: `-ss` antes de `-i` + `-t <duración>` |
| 3 | **La config se congela al importar** y se importa por valor en los submódulos | `config.py`, `local/llm.py:2`, `local/transcriber.py:11` | Imposible cambiar modelo/provider en runtime desde un proceso servidor | Cada job corre en un **proceso hijo** con el env ya resuelto |
| 4 | **`generate_shorts()` no acepta `llm_fn` ni callbacks de progreso**; `_run_local` hardcodea `call_local_llm` | `pipeline.py:24-27` | No se puede inyectar el provider de la app ni mostrar progreso real | El `ProcessingService` orquesta las mismas funciones del core etapa por etapa e inyecta `llm_fn`. `generate_shorts` queda intacto para la CLI |
| 5 | **`detect_content_type` atrapa toda excepción** y devuelve un fallback | `highlights.py:167-171` | Una API key inválida parece éxito; el error real aparece recién en la llamada siguiente y con peor contexto | Preflight del provider antes de arrancar el job + mapeo de errores a mensajes en es-AR |
| 6 | **Nombres de salida fijos** `short_01.mp4`… en un único directorio | `local/clipper.py:153` | Dos proyectos se pisan los clips | Se pasa `out_dir` por proyecto (el parámetro ya existe) |
| 7 | **Cache de transcripción por *stem* del archivo** | `local/transcriber.py:14-18` | Dos videos distintos llamados `input.mp4` comparten transcripción; además el `.srt` cae en la carpeta de resultados del usuario | Cache por proyecto, en un directorio propio del job |
| 8 | **Sin chequeo previo de `ffmpeg`** | `local/clipper.py` | El pipeline muere con `FileNotFoundError` recién en el primer clip, después de descargar y transcribir | Preflight de ffmpeg antes de encolar el job + estado en Diagnóstico |
| 9 | `main.py` abre el JSON de salida sin `encoding="utf-8"` | `main.py:65` | Puede fallar con títulos no-ASCII en Windows | No se toca (fuera de alcance; anotado) |
| 10 | El audio se muxea con `-map 1:a:0?` desde el clip cortado, con `-shortest` | `local/clipper.py:110-119` | Si el frame count del reframe difiere, el audio se puede truncar unos frames | No se toca (comportamiento upstream aceptable) |

## 13. Lo que Andy Clip **no** cambia del core

- Los prompts (`VIRALITY_CRITERIA`, `HIGHLIGHT_SYSTEM_PROMPT`) y sus parámetros.
- El chunking, el dedupe y el sanitizado de highlights.
- La lógica de cache de descarga y de transcripción.
- El modo `api` / MuAPI completo.
- La firma y el comportamiento de `generate_shorts()` y del CLI.
- La detección de caras y el smoothing del reframe.

El detalle exacto de los parches al core está en [`UPSTREAM.md`](UPSTREAM.md).
