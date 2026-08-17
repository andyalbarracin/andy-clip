import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";
import "./ui.css";

import type { ComponentStatus } from "../types/api";

/* ── Botón ────────────────────────────────────────────────────────────────*/

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  children,
  className = "",
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`btn btn--${variant} btn--${size} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ── Estado de un componente del sistema ──────────────────────────────────*/

const STATUS_LABEL: Record<ComponentStatus, string> = {
  available: "Disponible",
  configured: "Configurado",
  not_configured: "No configurado",
  not_detected: "No detectado",
  error: "Error",
};

/**
 * El estado nunca depende solo del color: el punto cambia de forma y siempre
 * viene con su palabra al lado.
 */
export function StatusDot({ status }: { status: ComponentStatus }) {
  return (
    <span className={`dot dot--${status}`} aria-hidden="true">
      {status === "not_detected" || status === "error" ? "×" : ""}
    </span>
  );
}

export function StatusLabel({ status }: { status: ComponentStatus }) {
  return <>{STATUS_LABEL[status] ?? status}</>;
}

/* ── Panel ────────────────────────────────────────────────────────────────*/

export function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || action) && (
        <header className="panel__head">
          {typeof title === "string" ? <h2>{title}</h2> : title}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/* ── Vacíos ───────────────────────────────────────────────────────────────*/

export function EmptyState({
  title,
  hint,
  cta,
}: {
  title: string;
  hint?: string;
  cta?: { label: string; to: string };
}) {
  return (
    <div className="empty">
      <p className="empty__title">{title}</p>
      {hint && <p className="empty__hint">{hint}</p>}
      {cta && (
        <Link className="btn btn--primary btn--md" to={cta.to}>
          {cta.label}
        </Link>
      )}
    </div>
  );
}

/* ── Campo de formulario ──────────────────────────────────────────────────*/

export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: ReactNode;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label className="field__label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && <p className="field__hint">{hint}</p>}
    </div>
  );
}

/* ── Error que no deja a nadie en un callejón ─────────────────────────────*/

export function ErrorNote({
  message,
  action,
}: {
  message: string;
  action?: string;
}) {
  const target = action?.startsWith("settings") ? "/configuracion" : null;
  return (
    <p className="error-note" role="alert">
      {message}
      {target && (
        <Link className="error-note__link" to={target}>
          Ir a configuración
        </Link>
      )}
    </p>
  );
}
