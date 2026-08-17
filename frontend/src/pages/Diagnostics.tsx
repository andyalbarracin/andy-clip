import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import { Panel, StatusDot, StatusLabel } from "../components/ui";
import "./Diagnostics.css";

export function Diagnostics() {
  const { data, isLoading } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => api.systemStatus(),
  });

  return (
    <div className="diagnostics">
      <h1>Diagnóstico</h1>
      <p className="muted small">
        Qué encontramos en este equipo. No hacemos ninguna llamada paga para armar esta
        lista: solo miramos qué hay instalado y qué credenciales tenés cargadas.
      </p>

      <Panel>
        {isLoading && <p className="muted">Revisando…</p>}

        <ul className="diagnostics__list">
          {data?.components.map((component) => (
            <li key={component.id} className="diagnostics__item">
              <StatusDot status={component.status} />
              <span className="diagnostics__label">{component.label}</span>
              <span className="diagnostics__state">
                <StatusLabel status={component.status} />
              </span>
              <span className="diagnostics__version mono">{component.version ?? ""}</span>
              {component.detail && component.status !== "available" && (
                <p className="diagnostics__detail">{component.detail}</p>
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
