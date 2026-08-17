import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../lib/api";
import { Button, EmptyState, ErrorNote, Panel, TextInput } from "../components/ui";
import { ProjectRow } from "../components/ProjectRow";
import "./Projects.css";

export function Projects() {
  const queryClient = useQueryClient();
  const [renaming, setRenaming] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects(),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["projects"] });
    queryClient.invalidateQueries({ queryKey: ["home"] });
  };

  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.renameProject(id, name),
    onSuccess: () => {
      setRenaming(null);
      setError(null);
      refresh();
    },
    onError: (err: ApiError) => setError(err),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => {
      setConfirming(null);
      setError(null);
      refresh();
    },
    onError: (err: ApiError) => setError(err),
  });

  return (
    <div className="projects">
      <h1>Proyectos</h1>

      {error && <ErrorNote message={error.message} action={error.action} />}

      <Panel>
        {isLoading && <p className="muted">Cargando…</p>}

        {!isLoading && data?.projects.length === 0 && (
          <EmptyState
            title="Todavía no procesaste ningún video."
            hint="Cada video que proceses queda acá con su transcripción, sus momentos detectados y sus clips."
            cta={{ label: "Crear primer proyecto", to: "/procesar" }}
          />
        )}

        <ul className="stack">
          {data?.projects.map((project) => (
            <li key={project.id} className="projects__item">
              {renaming === project.id ? (
                <form
                  className="projects__rename"
                  onSubmit={(event) => {
                    event.preventDefault();
                    rename.mutate({ id: project.id, name: draftName });
                  }}
                >
                  <label className="sr-only" htmlFor={`nombre-${project.id}`}>
                    Nombre del proyecto
                  </label>
                  <TextInput
                    id={`nombre-${project.id}`}
                    value={draftName}
                    onChange={setDraftName}
                    autoFocus
                  />
                  <Button variant="primary" size="sm" type="submit" loading={rename.isPending}>
                    Guardar
                  </Button>
                  <Button size="sm" type="button" onClick={() => setRenaming(null)}>
                    Cancelar
                  </Button>
                </form>
              ) : confirming === project.id ? (
                <div className="projects__confirm">
                  <p>
                    ¿Eliminar «{project.name}» del historial? Los clips que ya generaste
                    y el video original quedan donde están.
                  </p>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => remove.mutate(project.id)}
                    loading={remove.isPending}
                  >
                    Eliminar del historial
                  </Button>
                  <Button size="sm" onClick={() => setConfirming(null)}>
                    Cancelar
                  </Button>
                </div>
              ) : (
                <div className="projects__row">
                  <ProjectRow project={project} />
                  <div className="projects__actions">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setRenaming(project.id);
                        setDraftName(project.name);
                      }}
                    >
                      Renombrar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirming(project.id)}
                    >
                      Eliminar
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
