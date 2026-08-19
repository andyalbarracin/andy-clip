import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Lozenge from "@atlaskit/lozenge";
import { Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { duration as formatDuration, timecode } from "../lib/format";
import { Button, Choice, EmptyState, ErrorNote, Field, Panel, TextInput } from "../components/ui";
import { CanvasPreview } from "../components/editor/CanvasPreview";
import { JobProgress } from "../components/JobProgress";
import { TrimTrack } from "../components/editor/TrimTrack";
import type { Highlight } from "../types/api";
import "./Editor.css";

const ACTIVE = ["pending", "queued", "processing"];

type Pestana = "encuadre" | "recorte" | "ajustes" | "subtitulos" | "filtros";

const PESTANAS: { id: Pestana; label: string; lista: boolean }[] = [
  { id: "encuadre", label: "Encuadre", lista: true },
  { id: "recorte", label: "Recorte", lista: true },
  { id: "ajustes", label: "Color y brillo", lista: false },
  { id: "subtitulos", label: "Subtítulos", lista: false },
  { id: "filtros", label: "Filtros", lista: false },
];

/**
 * Retocar un video ya procesado, viendo cómo va a quedar antes de generarlo.
 *
 * Nada de lo que se hace acá vuelve a descargar, transcribir ni llamar a la IA:
 * el video y los momentos ya están guardados. Cambiar encuadre o recorte cuesta
 * segundos y no gasta una llamada al proveedor, así que se puede probar sin
 * pensarlo dos veces.
 */
export function Editor() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const proyectoId = params.get("proyecto");

  const [pestana, setPestana] = useState<Pestana>("encuadre");
  const [momentoId, setMomentoId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [cabeza, setCabeza] = useState(0);
  const [duracionFuente, setDuracionFuente] = useState(0);
  const [buscar, setBuscar] = useState<number | undefined>();
  const video = useRef<HTMLVideoElement | null>(null);

  // Ajustes que se están probando; empiezan en los del proyecto.
  const [framing, setFraming] = useState<string | null>(null);
  const [background, setBackground] = useState<string | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [aspect, setAspect] = useState<string | null>(null);

  const { data: listado } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects(),
  });

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.settings(),
  });

  const { data } = useQuery({
    queryKey: ["project", proyectoId],
    queryFn: () => api.project(proyectoId as string),
    enabled: Boolean(proyectoId),
    refetchInterval: (query) =>
      ACTIVE.includes(query.state.data?.job?.status ?? "") ? 1500 : false,
  });

  useEffect(() => {
    setFraming(null);
    setBackground(null);
    setColor(null);
    setAspect(null);
    setMomentoId(null);
    setError(null);
  }, [proyectoId]);

  const proyecto = data?.project;
  const job = data?.job;
  const ocupado = ACTIVE.includes(job?.status ?? "");
  const options = settings?.options;

  const editables = useMemo(
    () => (listado?.projects ?? []).filter((p) => p.media_path || p.status === "done"),
    [listado],
  );

  const momentos = data?.highlights ?? [];
  const momento: Highlight | undefined =
    momentos.find((h) => h.id === momentoId) ?? momentos.find((h) => h.selected) ?? momentos[0];

  const valor = {
    framing: framing ?? proyecto?.settings.framing ?? "faces",
    background: background ?? proyecto?.settings.background ?? "blur",
    color: color ?? proyecto?.settings.background_color ?? "#0A0B0C",
    aspect: aspect ?? proyecto?.settings.aspect_ratio ?? "9:16",
  };

  const recortar = useMutation({
    mutationFn: ({ id, inicio, fin }: { id: string; inicio: number; fin: number }) =>
      api.updateHighlight(proyectoId as string, id, { start_time: inicio, end_time: fin }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", proyectoId] }),
    onError: (err: ApiError) => setError(err),
  });

  const alternar = useMutation({
    mutationFn: ({ id, elegido }: { id: string; elegido: boolean }) =>
      api.updateHighlight(proyectoId as string, id, { selected: elegido }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", proyectoId] }),
    onError: (err: ApiError) => setError(err),
  });

  const aplicar = useMutation({
    mutationFn: () =>
      api.rerenderProject(proyectoId as string, {
        framing: valor.framing,
        background: valor.background,
        background_color: valor.color,
        aspect_ratio: valor.aspect,
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["project", proyectoId] });
    },
    onError: (err: ApiError) => setError(err),
  });

  const elegidos = momentos.filter((h) => h.selected).length;

  function reproducir() {
    const nodo = video.current;
    if (!nodo) return;
    if (nodo.paused) {
      void nodo.play();
      setReproduciendo(true);
    } else {
      nodo.pause();
      setReproduciendo(false);
    }
  }

  return (
    <div className="editor">
      <header className="editor__bar">
        <h1>Editor</h1>

        <div className="editor__picker">
          <label className="sr-only" htmlFor="ed-proyecto">
            Video a editar
          </label>
          <Choice
            id="ed-proyecto"
            value={proyectoId ?? ""}
            onChange={(id) => setParams({ proyecto: id })}
            options={editables.map((p) => ({ value: p.id, label: p.name }))}
          />
        </div>

        <Button
          variant="primary"
          onClick={() => aplicar.mutate()}
          loading={aplicar.isPending}
          disabled={!proyectoId || ocupado || elegidos === 0}
        >
          Generar {elegidos > 0 ? `${elegidos} clips` : "clips"}
        </Button>
      </header>

      {error && <ErrorNote message={error.message} action={error.action} />}

      {editables.length === 0 && (
        <Panel>
          <EmptyState
            title="Todavía no hay videos para editar."
            hint="Procesá un video y después volvé acá para ajustar el encuadre y el recorte."
            cta={{ label: "Procesar un video", to: "/procesar" }}
          />
        </Panel>
      )}

      {!proyectoId && editables.length > 0 && (
        <Panel>
          <EmptyState title="Elegí arriba el video que querés editar." />
        </Panel>
      )}

      {proyectoId && proyecto && (
        <div className="editor__layout">
          {/* ── Momentos ─────────────────────────────────────────────── */}
          <Panel title="Momentos" className="editor__moments">
            {momentos.length === 0 ? (
              <EmptyState title="Este video todavía no tiene momentos detectados." />
            ) : (
              <ul className="editor__moment-list">
                {momentos.map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      className={`editor__moment${h.id === momento?.id ? " is-active" : ""}`}
                      onClick={() => {
                        setMomentoId(h.id);
                        setBuscar(h.start_time);
                      }}
                    >
                      <span className="editor__moment-top">
                        <span className="editor__moment-score mono">{h.score}</span>
                        <span className="editor__moment-title">{h.title}</span>
                      </span>
                      <span className="editor__moment-meta mono">
                        {timecode(h.start_time)} · {formatDuration(h.duration)}
                      </span>
                    </button>
                    <label className="editor__moment-toggle">
                      <input
                        type="checkbox"
                        checked={h.selected}
                        onChange={(event) =>
                          alternar.mutate({ id: h.id, elegido: event.target.checked })
                        }
                      />
                      {h.selected ? "Se genera" : "No se genera"}
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* ── Lienzo ───────────────────────────────────────────────── */}
          <div className="editor__stage">
            {proyecto.media_path ? (
              <>
                <CanvasPreview
                  src={api.projectMediaUrl(proyecto.id)}
                  aspectRatio={valor.aspect}
                  framing={valor.framing}
                  background={valor.background}
                  backgroundColor={valor.color}
                  seekTo={buscar}
                  videoRef={video}
                  onDuration={setDuracionFuente}
                  onTime={setCabeza}
                />

                <div className="editor__transport">
                  <Button size="sm" onClick={reproducir}>
                    {reproduciendo ? <Pause size={14} /> : <Play size={14} />}
                    {reproduciendo ? "Pausar" : "Reproducir"}
                  </Button>
                  <span className="mono editor__clock">
                    {timecode(cabeza)} / {timecode(duracionFuente)}
                  </span>
                  <Lozenge appearance="default">{valor.aspect}</Lozenge>
                </div>
              </>
            ) : (
              <Panel>
                <EmptyState
                  title="Este proyecto se procesó antes de que guardáramos el video original."
                  hint="Para poder editarlo con vista previa, procesalo de nuevo."
                />
              </Panel>
            )}
          </div>

          {/* ── Ajustes ──────────────────────────────────────────────── */}
          <Panel className="editor__tools">
            <nav className="editor__tabs" aria-label="Herramientas de edición">
              {PESTANAS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`editor__tab${pestana === item.id ? " is-active" : ""}`}
                  onClick={() => item.lista && setPestana(item.id)}
                  disabled={!item.lista}
                  title={item.lista ? undefined : "Todavía no está disponible"}
                >
                  {item.label}
                </button>
              ))}
            </nav>

            {pestana === "encuadre" && (
              <div className="editor__controls">
                <Field label="Formato" htmlFor="ed-aspect">
                  <Choice
                    id="ed-aspect"
                    value={valor.aspect}
                    onChange={setAspect}
                    options={(options?.aspect_ratios ?? ["9:16"]).map((r) => ({
                      value: r,
                      label: r,
                    }))}
                  />
                </Field>

                <Field
                  label="Encuadre"
                  htmlFor="ed-framing"
                  hint={
                    valor.framing === "fit"
                      ? "El video entra entero: no se pierden zócalos ni subtítulos quemados."
                      : "Recorta a vertical. Lo que quede fuera del cuadro se pierde."
                  }
                >
                  <Choice
                    id="ed-framing"
                    value={valor.framing}
                    onChange={setFraming}
                    options={(options?.framings ?? []).map((f) => ({
                      value: f.id,
                      label: f.label,
                    }))}
                  />
                </Field>

                {valor.framing === "fit" && (
                  <Field label="Relleno de arriba y abajo" htmlFor="ed-background">
                    <Choice
                      id="ed-background"
                      value={valor.background}
                      onChange={setBackground}
                      options={(options?.backgrounds ?? []).map((b) => ({
                        value: b.id,
                        label: b.label,
                      }))}
                    />
                  </Field>
                )}

                {valor.framing === "fit" && valor.background !== "blur" && (
                  <Field label="Color del relleno" htmlFor="ed-color">
                    <TextInput
                      id="ed-color"
                      type="color"
                      value={valor.color}
                      onChange={(v) => setColor(v.toUpperCase())}
                    />
                  </Field>
                )}
              </div>
            )}

            {pestana === "recorte" && momento && (
              <div className="editor__trim">
                <p className="muted small">
                  Ajustá dónde empieza y termina «{momento.title}». Arrastrá los extremos
                  o hacé clic en la barra para mover la reproducción.
                </p>

                <TrimTrack
                  duration={duracionFuente || proyecto.duration || 0}
                  start={momento.start_time}
                  end={momento.end_time}
                  playhead={cabeza}
                  onSeek={(segundo) => setBuscar(segundo)}
                  onChange={(inicio, fin) =>
                    recortar.mutate({ id: momento.id, inicio, fin })
                  }
                />

                <div className="editor__trim-actions">
                  <Button
                    size="sm"
                    onClick={() =>
                      recortar.mutate({
                        id: momento.id,
                        inicio: Math.min(cabeza, momento.end_time - 0.5),
                        fin: momento.end_time,
                      })
                    }
                  >
                    Entrada acá
                  </Button>
                  <Button
                    size="sm"
                    onClick={() =>
                      recortar.mutate({
                        id: momento.id,
                        inicio: momento.start_time,
                        fin: Math.max(cabeza, momento.start_time + 0.5),
                      })
                    }
                  >
                    Salida acá
                  </Button>
                  <span className="muted small">
                    Los cambios se guardan al soltar; generá para verlos aplicados.
                  </span>
                </div>
              </div>
            )}

            {pestana === "recorte" && !momento && (
              <EmptyState title="Elegí un momento de la izquierda para recortarlo." />
            )}
          </Panel>

          {/* ── Estado y resultado ───────────────────────────────────── */}
          {job && (ocupado || job.status === "failed") && (
            <Panel className="editor__job">
              <JobProgress job={job} cancelling={false} onCancel={() => {}} />
            </Panel>
          )}

          {data && data.clips.length > 0 && (
            <Panel title="Clips generados" className="editor__results">
              <ul className="editor__clips">
                {data.clips.map((clip) => (
                  <li key={clip.id} className="editor__clip">
                    {clip.path ? (
                      <video
                        className="editor__clip-video"
                        src={api.clipFileUrl(clip.id)}
                        controls
                        preload="metadata"
                      />
                    ) : (
                      <div className="editor__clip-video editor__clip-video--failed">
                        {clip.error ?? "No se pudo generar"}
                      </div>
                    )}
                    <span className="editor__clip-meta mono">
                      {formatDuration(clip.duration)} · {clip.aspect_ratio}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}
