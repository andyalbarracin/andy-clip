# CLAUDE.md — Andy Clip

Reglas permanentes para cualquier sesión de Claude Code sobre este proyecto.
Estas reglas tienen prioridad sobre defaults del modelo.

## 1. PROJECT_ROOT IS THE FILESYSTEM BOUNDARY

PROJECT_ROOT is the directory containing this file (`.../code/andy-clip`).

- Never read, enumerate, modify, create or delete files outside PROJECT_ROOT unless the user explicitly authorizes it.
- Never inspect `~`, Desktop, Documents, Downloads, other repos, dotfiles, SSH keys, credentials or other VS Code / Claude configurations.
- Never use external temp directories to store permanent project content.

**Excepción de producto, no de permisos:** la aplicación final SÍ puede permitir que el
usuario elija un archivo externo mediante un file picker. Eso es funcionalidad de la app.
Claude sigue sin poder inspeccionar esos archivos.

## 2. Sistema

- Never use `sudo`.
- Never install global dependencies (`npm install -g`, `pip install` contra Python global, `brew install`).
- Never modify global configuration: Homebrew, apt, npm, pip, dotfiles, shell profiles, Git global, servicios del sistema.
- Never run remote scripts (`curl ... | sh`).
- Si falta una dependencia de sistema (ej. FFmpeg): detectarla, informarla, documentar cómo instalarla, y continuar con todo lo demás. No instalarla sin autorización expresa.
- Chequeos no destructivos de versión (`ffmpeg -version`, `node --version`) sí están permitidos.

## 3. Git

```
origin   = https://github.com/andyalbarracin/andy-clip.git
upstream = https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator.git
```

- Development happens directly on `main`. Do not create branches unless explicitly requested. Do not switch branches.
- Verificar `git branch --show-current` antes de modificar código.
- Commits locales sobre `main` están permitidos como checkpoints.
- **Never push without explicit authorization** (`git push`, `git push origin main`).
- **Never push to upstream.** Never open PRs to upstream. Never modify upstream config.
- Never pull, merge or rebase upstream automatically.
- Never `git push --force`, `git reset --hard`, `git clean -fd` without explicit authorization.
- Never rewrite history, delete commits, tags or remotes, or change remote URLs.
- Si `git status` muestra cambios que no hiciste vos: no los borres ni los sobrescribas. Asumí que son trabajo del usuario.
- Nunca commitear: `.env`, secrets, videos, `output/`, `temp/`, bases locales, caches.
- El repositorio YA está clonado. Nunca `git clone` ni `git init`.

## 4. Entornos y rutas

| Qué | Dónde |
|---|---|
| Python deps | `PROJECT_ROOT/.venv/` |
| Frontend deps | `PROJECT_ROOT/frontend/node_modules/` |
| Outputs (clips) | `PROJECT_ROOT/output/` |
| Temporales | `PROJECT_ROOT/temp/` |
| Datos locales (SQLite) | `PROJECT_ROOT/data/` |
| Config privada / secrets | `PROJECT_ROOT/.local/` |

Python del proyecto: **3.9.6** (única versión disponible en este equipo).
No usar sintaxis 3.10+: nada de `X | Y` en anotaciones, `list[str]`, `match`.
Usar `typing.Optional`, `typing.List`, `typing.Dict`, y `from __future__ import annotations` cuando ayude.

## 5. Secrets

- Never expose API keys. Never log secrets, tokens o `Authorization` headers.
- Las API keys viven en `.local/secrets.json` (gitignored, permisos `0600`), gestionadas por `SecretsService`.
- El backend nunca devuelve una key completa al frontend: solo versión masked (`sk-•••••4F2A`) y un booleano de presencia.
- Nunca guardar keys en `localStorage`, `sessionStorage`, `IndexedDB`, query params, URLs, logs, ni en el bundle del frontend.
- Nunca inventar API keys.
- No almacenar API keys en SQLite.

## 6. Llamadas pagas

- **Do not perform paid API calls automatically.** Ni OpenAI, ni Gemini, ni MuAPI.
- En tests: siempre mocks.
- Una llamada real solo puede ocurrir cuando el usuario lo pide expresamente o pulsa "Probar conexión" en la app.

## 7. Producto

- La UI visible debe estar en **español de Argentina (es-AR)**: voseo (`Elegí`, `Guardá`, `Configurá`, `Probá`), lenguaje natural, sin traducciones formales o artificiales. Los logs internos quedan en inglés.
- Nombre del producto: **Andy Clip**, centralizado en configuración (no hardcodeado).
- El modo predeterminado es **local**. MuAPI queda como servicio externo opcional; no se elimina.
- La app **no agrega** watermarks, logos, intros, outros ni branding a los clips exportados.
- Sin telemetría, analytics ni tracking. Sin login, usuarios, auth, pagos ni cloud. V1 es local y single-user.
- Backend escucha en `127.0.0.1` por defecto, nunca `0.0.0.0` salvo configuración explícita.
- CORS solo con origins locales necesarios; nunca wildcard.

## 8. Core

- **Preserve compatibility with the original Python core and CLI.** Debe seguir funcionando:
  - `python main.py "URL" --mode local`
  - `from shorts_generator import generate_shorts`
- No reescribir el motor desde cero. No portar la lógica Python a JavaScript.
- Arquitectura: `core original → capa de servicios → backend local → frontend`.
- Cambios al core: mínimos, quirúrgicos y documentados en `docs/UPSTREAM.md`.

## 9. Seguridad de backend

- Validar paths, uploads, extensiones, aspect ratios, cantidad de clips, IDs, nombres de archivo. Prevenir path traversal.
- Nunca `subprocess` con `shell=True` sobre contenido controlado por el usuario. Usar `subprocess.run([...])` con lista de argumentos.
- Errores de UI: nunca mostrar solo `500 Internal Server Error`. Traducir errores conocidos a mensajes accionables en es-AR.

## 10. Licencia y atribución

- No eliminar créditos, avisos ni atribución a upstream.
- No declarar una licencia nueva ni afirmar derechos de relicenciamiento sin verificar.

## 11. Antes de operaciones destructivas

Detenerse y pedir autorización expresa antes de: borrar archivos importantes, resetear Git,
sobrescribir trabajo, modificar remotes, eliminar grandes cantidades de datos, instalar
software global, salir de PROJECT_ROOT, acceder al keychain del OS, o ejecutar una API paga.
