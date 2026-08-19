import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { shortDate, shortSource } from "../lib/format";
import { Button, ButtonLink, EmptyState, Panel, TextInput } from "../components/ui";
import { FilePicker } from "../components/FilePicker";
import { ProjectRow } from "../components/ProjectRow";
import "./Home.css";

export function Home() {
  const navigate = useNavigate();
  const [source, setSource] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["home"],
    queryFn: () => api.home(),
  });

  const needsProvider = data?.local_mode.missing.includes("un proveedor de IA") ?? false;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const value = source.trim();
    if (!value) return;
    navigate(`/procesar?source=${encodeURIComponent(value)}`);
  }

  return (
    <div className="home">
      {needsProvider && (
        <div className="onboarding">
          <p>
            Configurá un proveedor de IA para analizar los mejores momentos de tus
            videos.
          </p>
          <ButtonLink to="/configuracion" variant="primary" size="sm">
            Configurar IA
          </ButtonLink>
        </div>
      )}

      {/* Lo primero es la acción: a esto viniste. */}
      <form className="start" onSubmit={submit}>
        <h1>Nuevo proyecto</h1>
        <div className="start__row">
          <label className="sr-only" htmlFor="source-inicio">
            Origen del video
          </label>
          <TextInput
            id="source-inicio"
            value={source}
            onChange={setSource}
            placeholder="Pegá el link de YouTube o la ruta de un video de tu equipo"
          />
          <FilePicker onPicked={(path) => navigate(`/procesar?source=${encodeURIComponent(path)}`)} />
          <Button variant="primary" type="submit" disabled={!source.trim()}>
            Continuar
            <ArrowRight size={15} strokeWidth={2} aria-hidden="true" />
          </Button>
        </div>
      </form>

      <Panel
        title="Proyectos recientes"
        action={
          data && data.total_projects > 0 ? (
            <Link className="link-quiet" to="/proyectos">
              Ver todos ({data.total_projects})
            </Link>
          ) : null
        }
      >
        {isLoading && <p className="muted">Cargando…</p>}

        {!isLoading && data?.recent_projects.length === 0 && (
          <EmptyState
            title="Todavía no procesaste ningún video."
            hint="Pegá un link arriba y en unos minutos vas a tener los mejores momentos recortados en vertical."
          />
        )}

        {data && data.recent_projects.length > 0 && (
          <ul className="stack">
            {data.recent_projects.map((project) => (
              <li key={project.id}>
                <ProjectRow project={project} />
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {data && data.recent_clips.length > 0 && (
        <Panel title="Clips recientes">
          <ul className="clip-strip">
            {data.recent_clips.map((clip) => (
              <li key={clip.id} className="clip-strip__item">
                <video
                  className="clip-strip__video"
                  src={api.clipFileUrl(clip.id)}
                  controls
                  preload="metadata"
                />
                <p className="clip-strip__name">{clip.project_name}</p>
                <p className="clip-strip__meta mono">{shortDate(clip.created_at)}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data && data.recent_projects.length > 0 && (
        <p className="muted small">
          Último origen procesado: {shortSource(data.recent_projects[0].source)}
        </p>
      )}
    </div>
  );
}
