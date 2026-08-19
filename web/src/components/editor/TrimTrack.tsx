import { useCallback, useRef } from "react";

import { timecode } from "../../lib/format";
import "./TrimTrack.css";

interface Props {
  duration: number;
  start: number;
  end: number;
  playhead: number;
  onChange: (start: number, end: number) => void;
  onSeek: (seconds: number) => void;
}

/**
 * Dónde empieza y dónde termina el clip, sobre la duración del video entero.
 *
 * Se puede arrastrar cada extremo o hacer clic en la barra para mover la
 * cabeza de reproducción. Los tiempos se muestran siempre: arrastrar es cómodo
 * pero impreciso, y a veces hace falta saber el segundo exacto.
 */
export function TrimTrack({ duration, start, end, playhead, onChange, onSeek }: Props) {
  const track = useRef<HTMLDivElement>(null);
  const total = duration > 0 ? duration : 1;

  const segundosEn = useCallback(
    (clientX: number) => {
      const caja = track.current?.getBoundingClientRect();
      if (!caja) return 0;
      const proporcion = Math.min(1, Math.max(0, (clientX - caja.left) / caja.width));
      return proporcion * total;
    },
    [total],
  );

  const arrastrar = (extremo: "start" | "end") => (event: React.PointerEvent) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);

    const mover = (movimiento: PointerEvent) => {
      const segundo = segundosEn(movimiento.clientX);
      // Medio segundo de separación mínima: un clip de cero no existe.
      if (extremo === "start") {
        onChange(Math.min(segundo, end - 0.5), end);
      } else {
        onChange(start, Math.max(segundo, start + 0.5));
      }
      onSeek(segundo);
    };

    const soltar = () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
    };

    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
  };

  const porcentaje = (segundo: number) => `${(segundo / total) * 100}%`;

  return (
    <div className="trim">
      <div
        ref={track}
        className="trim__track"
        onPointerDown={(event) => {
          if (event.target === track.current) onSeek(segundosEn(event.clientX));
        }}
      >
        <div
          className="trim__selection"
          style={{ left: porcentaje(start), width: porcentaje(end - start) }}
        />

        <div className="trim__playhead" style={{ left: porcentaje(playhead) }} />

        <button
          type="button"
          className="trim__handle trim__handle--start"
          style={{ left: porcentaje(start) }}
          onPointerDown={arrastrar("start")}
          aria-label="Comienzo del clip"
          title={`Comienzo: ${timecode(start)}`}
        />
        <button
          type="button"
          className="trim__handle trim__handle--end"
          style={{ left: porcentaje(end) }}
          onPointerDown={arrastrar("end")}
          aria-label="Final del clip"
          title={`Final: ${timecode(end)}`}
        />
      </div>

      <div className="trim__times mono">
        <span>{timecode(start)}</span>
        <span className="trim__duration">{timecode(end - start)} de clip</span>
        <span>{timecode(end)}</span>
      </div>
    </div>
  );
}
