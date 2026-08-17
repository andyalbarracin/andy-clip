import { Link } from "react-router-dom";

import { shortDate, shortSource } from "../lib/format";
import type { Project } from "../types/api";
import "./ProjectRow.css";

const STATUS: Record<Project["status"], { label: string; tone: string }> = {
  draft: { label: "Sin procesar", tone: "standby" },
  processing: { label: "Procesando", tone: "mark" },
  done: { label: "Listo", tone: "waveform" },
  failed: { label: "Falló", tone: "flag" },
  cancelled: { label: "Cancelado", tone: "standby" },
};

export function ProjectRow({ project }: { project: Project }) {
  const status = STATUS[project.status];

  return (
    <Link className="project-row" to={`/proyectos/${project.id}`}>
      <div className="project-row__main">
        <span className="project-row__name">{project.name}</span>
        <span className="project-row__source mono">{shortSource(project.source, 46)}</span>
      </div>

      <span className="project-row__specs mono">
        {project.settings.num_clips} clips · {project.settings.aspect_ratio}
      </span>

      <span className={`chip chip--${status.tone}`}>{status.label}</span>

      <span className="project-row__date mono">{shortDate(project.updated_at)}</span>
    </Link>
  );
}
