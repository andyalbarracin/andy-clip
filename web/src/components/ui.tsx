/**
 * Los componentes de la aplicación, construidos sobre Atlassian Design System.
 *
 * Esta capa existe para que las pantallas no hablen con `@atlaskit` directo:
 * traduce el vocabulario del producto ("primario", "peligro", "compacto") al de
 * la librería, y deja un único lugar donde ajustar si algo cambia.
 */
import AkButton, { LoadingButton } from "@atlaskit/button";
import { Label } from "@atlaskit/form";
import Heading from "@atlaskit/heading";
import Lozenge from "@atlaskit/lozenge";
import AkSelect from "@atlaskit/select";
import SectionMessage, { SectionMessageAction } from "@atlaskit/section-message";
import AkTextfield from "@atlaskit/textfield";
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { forwardRef } from "react";
import { Link } from "react-router-dom";

import type { ComponentStatus } from "../types/api";
import "./ui.css";

/* ── Botón ────────────────────────────────────────────────────────────────*/

type Variant = "primary" | "secondary" | "ghost" | "danger";

const APPEARANCE = {
  primary: "primary",
  secondary: "default",
  ghost: "subtle",
  danger: "danger",
} as const;

interface ButtonProps {
  variant?: Variant;
  size?: "sm" | "md";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: (event: MouseEvent<HTMLElement>) => void;
  children: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  children,
  disabled,
  onClick,
  type = "button",
}: ButtonProps) {
  const shared = {
    appearance: APPEARANCE[variant],
    spacing: size === "sm" ? ("compact" as const) : ("default" as const),
    isDisabled: disabled,
    onClick,
    type,
  };

  return loading ? (
    <LoadingButton {...shared} isLoading>
      {children}
    </LoadingButton>
  ) : (
    <AkButton {...shared}>{children}</AkButton>
  );
}

/**
 * Adaptador para que un botón de Atlassian navegue con el router en vez de
 * recargar la página entera.
 */
const RouterAnchor = forwardRef<HTMLAnchorElement, AnchorHTMLAttributes<HTMLAnchorElement>>(
  ({ href = "", ...rest }, ref) => <Link ref={ref} to={href} {...rest} />,
);
RouterAnchor.displayName = "RouterAnchor";

/** Un botón que navega. Mismo aspecto, pero es un enlace de verdad. */
export function ButtonLink({
  to,
  variant = "secondary",
  size = "md",
  children,
}: {
  to: string;
  variant?: Variant;
  size?: "sm" | "md";
  children: ReactNode;
}) {
  return (
    <AkButton
      appearance={APPEARANCE[variant]}
      spacing={size === "sm" ? "compact" : "default"}
      component={RouterAnchor}
      href={to}
    >
      {children}
    </AkButton>
  );
}

/** Descarga de un archivo: tiene que ser un ancla, no un botón. */
export function DownloadLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <AkButton href={href} download spacing="compact">
      {children}
    </AkButton>
  );
}

/* ── Campos ───────────────────────────────────────────────────────────────*/

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
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="field__hint">{hint}</p>}
    </div>
  );
}

export function TextInput({
  id,
  value,
  onChange,
  placeholder,
  type = "text",
  isMonospaced = false,
  ...rest
}: {
  id: string;
  /** Controlado. Para un campo que guarda al salir, usá `defaultValue` + `onBlur`. */
  value?: string | number;
  onChange?: (value: string) => void;
  placeholder?: string;
  type?: string;
  isMonospaced?: boolean;
  [key: string]: unknown;
}) {
  return (
    <AkTextfield
      id={id}
      name={id}
      value={value}
      type={type}
      placeholder={placeholder}
      isMonospaced={isMonospaced}
      onChange={
        onChange
          ? (event) => onChange((event.target as HTMLInputElement).value)
          : undefined
      }
      autoComplete="off"
      spellCheck={false}
      {...rest}
    />
  );
}

export interface Option {
  value: string;
  label: string;
  isDisabled?: boolean;
}

export function Choice({
  id,
  value,
  options,
  onChange,
}: {
  id: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
}) {
  const selected = options.find((option) => option.value === value) ?? null;

  return (
    <AkSelect<Option>
      inputId={id}
      value={selected}
      options={options}
      isSearchable={false}
      onChange={(option) => option && onChange(option.value)}
      isOptionDisabled={(option) => Boolean(option.isDisabled)}
    />
  );
}

/* ── Estructura ───────────────────────────────────────────────────────────*/

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
          {typeof title === "string" ? <Heading size="small">{title}</Heading> : title}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

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
        <ButtonLink to={cta.to} variant="primary">
          {cta.label}
        </ButtonLink>
      )}
    </div>
  );
}

/* ── Estados ──────────────────────────────────────────────────────────────*/

const STATUS_LABEL: Record<ComponentStatus, string> = {
  available: "Disponible",
  configured: "Configurado",
  not_configured: "No configurado",
  not_detected: "No detectado",
  error: "Error",
};

const STATUS_APPEARANCE = {
  available: "success",
  configured: "success",
  not_configured: "default",
  not_detected: "removed",
  error: "removed",
} as const;

/** Compacto, para el margen. El estado nunca depende solo del color. */
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

export function StatusTag({ status }: { status: ComponentStatus }) {
  return <Lozenge appearance={STATUS_APPEARANCE[status]}>{STATUS_LABEL[status]}</Lozenge>;
}

/* ── Errores ──────────────────────────────────────────────────────────────*/

export function ErrorNote({ message, action }: { message: string; action?: string }) {
  const target = action?.startsWith("settings") ? "/configuracion" : null;

  return (
    <div className="error-note" role="alert">
      <SectionMessage
        appearance="error"
        actions={
          target
            ? [
                <SectionMessageAction key="settings" href={target}>
                  Ir a configuración
                </SectionMessageAction>,
              ]
            : undefined
        }
      >
        {message}
      </SectionMessage>
    </div>
  );
}
