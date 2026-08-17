import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import Lozenge from "@atlaskit/lozenge";

import { api, ApiError } from "../lib/api";
import { duration, shortDate, timecode } from "../lib/format";
import { Button, DownloadLink, EmptyState, ErrorNote, Panel } from "../components/ui";
import { JobProgress } from "../components/JobProgress";
import { SourceTimeline } from "../components/SourceTimeline";
import "./ProjectDetail.css";

const ACTIVE = ["pending", "queued", "processing"];

export function ProjectDetail() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<ApiError | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["project", id],
    queryFn: () => api.project(id),
    // Mientras hay un trabajo en curso preguntamos seguido; cuando termina,
    // dejamos de molestar al backend.
    refetchInterval: (query) =>
      ACTIVE.includes(query.state.data?.job?.status ?? "") ? 1500 : false,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["project", id] });
    queryClient.invalidateQueries({ queryKey: ["home"] });
  };

  const process = useMutation({
    mutationFn: () => api.processProject(id),
    onSuccess: () => {
      setActionError(null);
      refresh();
    },
    onError: (err: ApiError) => setActionError(err),
  });

  const cancel = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: refresh,
    onError: (err: ApiError) => setActionError(err),
  });

  if (isLoading) return <p className="muted">Cargando…</p>;
  if (error) return <ErrorNote message={(error as Error).message} />;
  if (!data) return null;

  const { project, highlights, clips, job } = data;
  const total = project.duration ?? project.transcript?.duration ?? 0;
  const busy = ACTIVE.includes(job?.status ?? "");

  return (
    <div className="detail">
      <header className="detail__head">
        <div className="detail__title">
          <h1>{project.name}</h1>
          <Button
            variant="primary"
            onClick={() => process.mutate()}
            loading={process.isPending}
            disabled={busy}
          >
            {clips.length > 0 ? "Procesar de nuevo" : "Procesar"}
          </Button>
        </div>
        <p className="detail__source mono">{project.source}</p>
      </header>

      {actionError && <ErrorNote message={actionError.message} action={actionError.action} />}
      {project.error && !busy && <ErrorNote message={project.error} />}

      {job && (busy || job.status === "failed") && (
        <Panel>
          <JobProgress
            job={job}
            cancelling={cancel.isPending}
            onCancel={() => cancel.mutate(job.id)}
          />
        </Panel>
      )}

      {/* La barra del material: dónde cae cada momento dentro del video. */}
      {total > 0 && highlights.length > 0 && (
        <Panel title="Mapa del video">
          <SourceTimeline
            duration={total}
            size="lg"
            segments={highlights.map((highlight) => ({
              id: highlight.id,
              start: highlight.start_time,
              end: highlight.end_time,
              selected: highlight.selected,
              title: highlight.title,
              score: highlight.score,
            }))}
          />
          <p className="detail__legend">
            <span className="detail__legend-key detail__legend-key--selected" />
            Elegidos para recortar
            <span className="detail__legend-key detail__legend-key--discarded" />
            Detectados pero descartados
            <span className="detail__legend-total mono">{duration(total)}</span>
          </p>
        </Panel>
      )}

      <Panel title="Clips">
        {clips.length === 0 ? (
          <EmptyState
            title="Este proyecto todavía no tiene clips."
            hint="Cuando el procesamiento termine vas a verlos acá, listos para reproducir y descargar."
          />
        ) : (
          <ul className="detail__clips">
            {clips.map((clip) => (
              <li key={clip.id} className="detail__clip">
                {clip.path ? (
                  <video
                    className="detail__video"
                    src={api.clipFileUrl(clip.id)}
                    controls
                    preload="metadata"
                  />
                ) : (
                  <div className="detail__video detail__video--failed">
                    <span>{clip.error ?? "No se pudo generar"}</span>
                  </div>
                )}
                {clip.path && (
                  <DownloadLink href={api.clipFileUrl(clip.id, true)}>Descargar</DownloadLink>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Momentos detectados">
        {highlights.length === 0 ? (
          <EmptyState title="Todavía no analizamos este video." />
        ) : (
          <ul className="detail__highlights">
            {highlights.map((highlight) => (
              <li key={highlight.id} className="detail__highlight">
                <span className="detail__score mono">{highlight.score}</span>
                <div className="detail__highlight-body">
                  <p className="detail__highlight-title">{highlight.title}</p>
                  {highlight.hook_sentence && (
                    <p className="detail__hook">«{highlight.hook_sentence}»</p>
                  )}
                  {highlight.virality_reason && (
                    <p className="detail__reason">{highlight.virality_reason}</p>
                  )}
                </div>
                <span className="detail__times mono">
                  {timecode(highlight.start_time)} → {timecode(highlight.end_time)}
                  <span className="detail__duration">{duration(highlight.duration)}</span>
                </span>
                <span className="detail__flag">
                  <Lozenge appearance={highlight.selected ? "inprogress" : "default"}>
                    {highlight.selected ? "Elegido" : "Descartado"}
                  </Lozenge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Transcripción">
        {!project.transcript || project.transcript.segments.length === 0 ? (
          <EmptyState title="Todavía no transcribimos este video." />
        ) : (
          <ol className="detail__transcript">
            {project.transcript.segments.map((segment, index) => (
              <li key={index} className="detail__segment">
                <span className="detail__timecode mono">{timecode(segment.start)}</span>
                <p>{segment.text}</p>
              </li>
            ))}
          </ol>
        )}
      </Panel>

      <p className="muted small">
        Creado el {shortDate(project.created_at)} · {project.settings.num_clips} clips ·{" "}
        {project.settings.aspect_ratio} · {project.settings.resolution}p · modo{" "}
        {project.settings.mode}
      </p>
    </div>
  );
}
