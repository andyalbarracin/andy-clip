import { useQuery } from "@tanstack/react-query";
import Spinner from "@atlaskit/spinner";

import { api } from "../lib/api";
import type { Job } from "../types/api";
import { Button } from "./ui";
import "./JobProgress.css";

const ACTIVE = ["pending", "queued", "processing"];

/**
 * El pipeline como una lista de etapas, no como una barra que avanza sola.
 *
 * Ninguna de estas etapas expone un avance medible, así que decimos en cuál
 * está y listo. Inventar un porcentaje sería mentirle a alguien que está
 * decidiendo si esperar o cancelar.
 */
export function JobProgress({
  job,
  onCancel,
  cancelling,
}: {
  job: Job;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const { data } = useQuery({
    queryKey: ["stages"],
    queryFn: () => api.stages(),
    staleTime: Infinity,
  });

  const stages = (data?.stages ?? []).filter((stage) => stage.id !== "finished");
  const currentIndex = stages.findIndex((stage) => stage.id === job.stage);
  const isActive = ACTIVE.includes(job.status);

  return (
    <div className="job">
      <header className="job__head">
        <span className="job__state">
          {isActive && <Spinner size="small" />}
          {job.message ?? job.stage_label ?? job.status_label}
        </span>

        {isActive && (
          <Button variant="ghost" size="sm" onClick={onCancel} loading={cancelling}>
            Cancelar
          </Button>
        )}
      </header>

      <ol className="job__stages">
        {stages.map((stage, index) => {
          const state =
            currentIndex < 0
              ? "pending"
              : index < currentIndex
                ? "done"
                : index === currentIndex
                  ? "current"
                  : "pending";

          return (
            <li key={stage.id} className={`job__stage is-${state}`}>
              <span className="job__bullet" aria-hidden="true">
                {state === "done" ? "✓" : state === "current" ? "▸" : ""}
              </span>
              {stage.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
