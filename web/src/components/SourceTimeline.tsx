import "./SourceTimeline.css";

export interface TimelineSegment {
  id: string;
  start: number;
  end: number;
  selected: boolean;
  title?: string;
  score?: number;
}

interface Props {
  duration: number;
  segments: TimelineSegment[];
  size?: "sm" | "md" | "lg";
  activeId?: string | null;
  onSelect?: (id: string) => void;
}

/**
 * La barra del video fuente: el mapa del material.
 *
 * Cada momento detectado se dibuja donde realmente cae dentro de la duración
 * del video, no en una grilla. Los elegidos van en ámbar; los descartados
 * quedan grises pero presentes, porque saber qué se dejó afuera es parte de
 * entender el resultado.
 *
 * Aparece en tres escalas: mínima en la tarjeta de un proyecto, mediana
 * mientras se procesa, y grande en los resultados.
 */
export function SourceTimeline({
  duration,
  segments,
  size = "md",
  activeId,
  onSelect,
}: Props) {
  const total = duration > 0 ? duration : 1;

  return (
    <div className={`timeline timeline--${size}`} role="group" aria-label="Momentos detectados sobre el video">
      <div className="timeline__track">
        {segments.map((segment) => {
          const left = (Math.max(0, segment.start) / total) * 100;
          const width = Math.max(
            0.8,
            ((Math.min(segment.end, total) - Math.max(0, segment.start)) / total) * 100,
          );
          const label = segment.title
            ? `${segment.title}${segment.score != null ? ` — ${segment.score} puntos` : ""}`
            : "Momento detectado";

          const className = [
            "timeline__segment",
            segment.selected ? "is-selected" : "is-discarded",
            activeId === segment.id ? "is-active" : "",
          ]
            .filter(Boolean)
            .join(" ");

          return onSelect ? (
            <button
              key={segment.id}
              type="button"
              className={className}
              style={{ left: `${left}%`, width: `${width}%` }}
              onClick={() => onSelect(segment.id)}
              aria-label={label}
              aria-pressed={activeId === segment.id}
            />
          ) : (
            <span
              key={segment.id}
              className={className}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={label}
            />
          );
        })}
      </div>
    </div>
  );
}
