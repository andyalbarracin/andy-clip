import Lozenge from "@atlaskit/lozenge";
import { Link } from "react-router-dom";

import { shortDate, shortSource } from "../lib/format";
import type { Project } from "../types/api";
import "./ProjectRow.css";

const STATUS: Record<
  Project["status"],
  { label: string; appearance: "default" | "inprogress" | "success" | "removed" }
> = {
  draft: { label: "Sin procesar", appearance: "default" },
  processing: { label: "Procesando", appearance: "inprogress" },
  done: { label: "Listo", appearance: "success" },
  failed: { label: "Falló", appearance: "removed" },
  cancelled: { label: "Cancelado", appearance: "default" },
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

      <span className="project-row__status">
        <Lozenge appearance={status.appearance}>{status.label}</Lozenge>
      </span>

      <span className="project-row__date mono">{shortDate(project.updated_at)}</span>
    </Link>
  );
}
