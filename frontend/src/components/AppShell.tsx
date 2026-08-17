import { useQuery } from "@tanstack/react-query";
import { Activity, Film, Home, Scissors, SlidersHorizontal } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { api } from "../lib/api";
import type { SystemComponent } from "../types/api";
import { StatusDot, StatusLabel } from "./ui";
import "./AppShell.css";

const NAV = [
  { to: "/", label: "Inicio", icon: Home, end: true },
  { to: "/proyectos", label: "Proyectos", icon: Film, end: false },
  { to: "/procesar", label: "Procesar video", icon: Scissors, end: false },
  { to: "/configuracion", label: "Configuración", icon: SlidersHorizontal, end: false },
];

/** Los tres componentes que definen si se puede procesar algo hoy. */
const ESSENTIAL = ["ffmpeg", "faster_whisper", "openai", "gemini"];

export function AppShell() {
  const { data } = useQuery({
    queryKey: ["system-summary"],
    queryFn: () => api.systemStatus(),
    staleTime: 30_000,
  });

  const components: SystemComponent[] = (data?.components ?? []).filter((component) =>
    ESSENTIAL.includes(component.id),
  );

  return (
    <div className="shell">
      <aside className="rail">
        {/* Marca tipográfica, no un logo: la aplicación todavía no necesita uno. */}
        <div className="rail__mark">
          Andy<span className="rail__mark-accent">Clip</span>
        </div>

        <nav aria-label="Secciones">
          <ul className="rail__nav">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `rail__link${isActive ? " is-active" : ""}`
                  }
                >
                  <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="rail__foot">
          <NavLink to="/configuracion/diagnostico" className="rail__diagnostics">
            <Activity size={14} strokeWidth={1.75} aria-hidden="true" />
            Diagnóstico
          </NavLink>
          <ul className="rail__system">
            {components.map((component) => (
              <li key={component.id} className="rail__system-item">
                <StatusDot status={component.status} />
                <span className="rail__system-label">{component.label}</span>
                <span className="rail__system-state">
                  <StatusLabel status={component.status} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="canvas">
        <Outlet />
      </main>
    </div>
  );
}
