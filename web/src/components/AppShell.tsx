import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Film,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Scissors,
  SlidersHorizontal,
  Wand2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { api } from "../lib/api";
import type { SystemComponent } from "../types/api";
import { StatusDot, StatusLabel } from "./ui";
import "./AppShell.css";

const NAV = [
  { to: "/", label: "Inicio", icon: Home, end: true },
  { to: "/proyectos", label: "Proyectos", icon: Film, end: false },
  { to: "/procesar", label: "Procesar video", icon: Scissors, end: false },
  { to: "/editor", label: "Editor", icon: Wand2, end: false },
  { to: "/configuracion", label: "Configuración", icon: SlidersHorizontal, end: false },
];

/** Los tres componentes que definen si se puede procesar algo hoy. */
const ESSENTIAL = ["ffmpeg", "faster_whisper", "openai", "gemini"];

const COLAPSADA = "andy-clip:barra-colapsada";

export function AppShell() {
  // La preferencia sobrevive a recargar: quien la colapsa la quiere colapsada.
  const [colapsada, setColapsada] = useState(
    () => localStorage.getItem(COLAPSADA) === "1",
  );

  useEffect(() => {
    localStorage.setItem(COLAPSADA, colapsada ? "1" : "0");
  }, [colapsada]);

  // Misma clave que usa Diagnóstico, y la misma que invalidan las pantallas al
  // guardar una credencial: si no coinciden, la barra lateral sigue mostrando
  // "No configurado" después de cargar una clave.
  const { data } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => api.systemStatus(),
    staleTime: 30_000,
  });

  const components: SystemComponent[] = (data?.components ?? []).filter((component) =>
    ESSENTIAL.includes(component.id),
  );

  return (
    <div className={`shell${colapsada ? " is-collapsed" : ""}`}>
      <aside className="rail">
        <div className="rail__head">
          {/* Marca tipográfica, no un logo: la aplicación todavía no necesita uno. */}
          <div className="rail__mark">
            {colapsada ? (
              <span className="rail__mark-accent">A</span>
            ) : (
              <>
                Andy<span className="rail__mark-accent">Clip</span>
              </>
            )}
          </div>

          <button
            type="button"
            className="rail__toggle"
            onClick={() => setColapsada((valor) => !valor)}
            aria-label={colapsada ? "Expandir la barra lateral" : "Colapsar la barra lateral"}
            aria-expanded={!colapsada}
            title={colapsada ? "Expandir" : "Colapsar"}
          >
            {colapsada ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>

        <nav aria-label="Secciones">
          <ul className="rail__nav">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  title={colapsada ? label : undefined}
                  className={({ isActive }) =>
                    `rail__link${isActive ? " is-active" : ""}`
                  }
                >
                  <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
                  <span className="rail__label">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="rail__foot">
          <NavLink
            to="/configuracion/diagnostico"
            className="rail__diagnostics"
            title={colapsada ? "Diagnóstico" : undefined}
          >
            <Activity size={14} strokeWidth={1.75} aria-hidden="true" />
            <span className="rail__label">Diagnóstico</span>
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

      <main className="workspace">
        <Outlet />
      </main>
    </div>
  );
}
