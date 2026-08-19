import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { duration, shortDate } from "../lib/format";
import { Button, Choice, EmptyState, ErrorNote, Field, Panel } from "../components/ui";
import { JobProgress } from "../components/JobProgress";
import "./Editor.css";

const ACTIVE = ["pending", "queued", "processing"];

/**
 * Retocar un proyecto que ya se procesó.
 *
 * Cambiar el encuadre no vuelve a descargar, transcribir ni analizar: el video
 * y los momentos ya están guardados, así que solo se recorta de nuevo. Cuesta
 * segundos y no gasta una llamada a la IA, y por eso se puede probar sin miedo.
 */
export function Editor() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const selected = params.get("proyecto");
  const [error, setError] = useState<ApiError | null>(null);

  const { data: listado } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects(),
  });

  const { data } = useQuery({
    queryKey: ["project", selected],
    queryFn: () => api.project(selected as string),
    enabled: Boolean(selected),
    refetchInterval: (query) =>
      ACTIVE.includes(query.state.data?.job?.status ?? "") ? 1500 : false,
  });

  // Los ajustes que se están probando, arrancando de lo que el proyecto tiene.
  const [framing, setFraming] = useState<string | null>(null);
  const [background, setBackground] = useState<string | null>(null);
  const [aspect, setAspect] = useState<string | null>(null);

  useEffect(() => {
    setFraming(null);
    setBackground(null);
    setAspect(null);
    setError(null);
  }, [selected]);

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.settings(),
  });

  const rerender = useMutation({
    mutationFn: () =>
      api.rerenderProject(selected as string, {
        ...(framing ? { framing } : {}),
        ...(background ? { background } : {}),
        ...(aspect ? { aspect_ratio: aspect } : {}),
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["project", selected] });
    },
    onError: (err: ApiError) => setError(err),
  });

  const conClips = (listado?.projects ?? []).filter((p) => p.status === "done");
  const proyecto = data?.project;
  const job = data?.job;
  const busy = ACTIVE.includes(job?.status ?? "");
  const options = settings?.options;

  const valor = {
    framing: framing ?? proyecto?.settings.framing ?? "faces",
    background: background ?? proyecto?.settings.background ?? "blur",
    aspect: aspect ?? proyecto?.settings.aspect_ratio ?? "9:16",
  };

  return (
    <div className="editor">
      <h1>Editor</h1>
      <p className="muted small">
        Retocá un video que ya procesaste. Cambiar el encuadre vuelve a generar
        los clips en segundos, sin descargar ni analizar de nuevo, y sin gastar
        una llamada a la IA.
      </p>

      {error && <ErrorNote message={error.message} action={error.action} />}

      <div className="editor__layout">
        <Panel title="Videos procesados" className="editor__list">
          {conClips.length === 0 ? (
            <EmptyState
              title="Todavía no hay videos procesados."
              hint="Cuando termines de procesar uno, va a aparecer acá para retocarlo."
              cta={{ label: "Procesar un video", to: "/procesar" }}
            />
          ) : (
            <ul className="editor__projects">
              {conClips.map((project) => (
                <li key={project.id}>
                  <button
                    type="button"
                    className={`editor__project${
                      project.id === selected ? " is-selected" : ""
                    }`}
                    onClick={() => setParams({ proyecto: project.id })}
                  >
                    <span className="editor__project-name">{project.name}</span>
                    <span className="editor__project-meta mono">
                      {project.settings.aspect_ratio} · {shortDate(project.updated_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="editor__work">
          {!proyecto && (
            <Panel>
              <EmptyState title="Elegí un video de la lista para retocarlo." />
            </Panel>
          )}

          {proyecto && (
            <>
              <Panel title="Ajustes">
                <div className="editor__controls">
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
                      options={(options?.framings ?? []).map((item) => ({
                        value: item.id,
                        label: item.label,
                      }))}
                    />
                  </Field>

                  {valor.framing === "fit" && (
                    <Field label="Relleno de arriba y abajo" htmlFor="ed-background">
                      <Choice
                        id="ed-background"
                        value={valor.background}
                        onChange={setBackground}
                        options={(options?.backgrounds ?? []).map((item) => ({
                          value: item.id,
                          label: item.label,
                        }))}
                      />
                    </Field>
                  )}

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
                </div>

                <div className="editor__apply">
                  <Button
                    variant="primary"
                    onClick={() => rerender.mutate()}
                    loading={rerender.isPending}
                    disabled={busy}
                  >
                    Aplicar y volver a generar
                  </Button>
                  <span className="muted small">
                    Se regeneran los {data?.highlights.filter((h) => h.selected).length ?? 0}{" "}
                    clips elegidos.
                  </span>
                </div>
              </Panel>

              {job && (busy || job.status === "failed") && (
                <Panel>
                  <JobProgress job={job} cancelling={false} onCancel={() => {}} />
                </Panel>
              )}

              <Panel title="Resultado">
                {data && data.clips.length > 0 ? (
                  <ul className="editor__clips">
                    {data.clips.map((clip) => (
                      <li key={clip.id} className="editor__clip">
                        {clip.path ? (
                          <video
                            className="editor__video"
                            src={`${api.clipFileUrl(clip.id)}#t=${clip.id}`}
                            controls
                            preload="metadata"
                          />
                        ) : (
                          <div className="editor__video editor__video--failed">
                            {clip.error ?? "No se pudo generar"}
                          </div>
                        )}
                        <span className="editor__clip-meta mono">
                          {duration(clip.duration)} · {clip.aspect_ratio}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState title="Este proyecto todavía no tiene clips." />
                )}
              </Panel>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
