import { useEffect, useRef } from "react";

import "./CanvasPreview.css";

interface Props {
  src: string;
  aspectRatio: string;
  framing: string;
  background: string;
  backgroundColor: string;
  /** Segundo del video original que hay que mostrar. */
  seekTo?: number;
  showGrid?: boolean;
  onDuration?: (seconds: number) => void;
  onTime?: (seconds: number) => void;
  videoRef?: React.MutableRefObject<HTMLVideoElement | null>;
}

function ratioValue(aspectRatio: string): number {
  const [w, h] = aspectRatio.split(":").map(Number);
  return w && h ? w / h : 9 / 16;
}

/**
 * Cómo va a quedar el clip, antes de generarlo.
 *
 * Reproduce el mismo encuadre que aplica FFmpeg: el lienzo tiene la relación de
 * aspecto elegida, y adentro el video se recorta o entra entero según el modo.
 * Para el relleno borroso se usa una segunda copia del video detrás, ampliada y
 * desenfocada — que es literalmente lo que hace el motor.
 */
export function CanvasPreview({
  src,
  aspectRatio,
  framing,
  background,
  backgroundColor,
  seekTo,
  showGrid = true,
  onDuration,
  onTime,
  videoRef,
}: Props) {
  const propio = useRef<HTMLVideoElement | null>(null);
  const principal = videoRef ?? propio;
  const fondo = useRef<HTMLVideoElement | null>(null);

  const entero = framing === "fit";

  // El fondo sigue al video principal. Es una previsualización: un desfase de
  // milisegundos no cambia ninguna decisión.
  useEffect(() => {
    const video = principal.current;
    const detras = fondo.current;
    if (!video || !detras) return;

    const sincronizar = () => {
      if (Math.abs(detras.currentTime - video.currentTime) > 0.2) {
        detras.currentTime = video.currentTime;
      }
    };
    const reproducir = () => {
      void detras.play().catch(() => {});
    };
    const pausar = () => detras.pause();

    video.addEventListener("timeupdate", sincronizar);
    video.addEventListener("play", reproducir);
    video.addEventListener("pause", pausar);
    video.addEventListener("seeked", sincronizar);
    return () => {
      video.removeEventListener("timeupdate", sincronizar);
      video.removeEventListener("play", reproducir);
      video.removeEventListener("pause", pausar);
      video.removeEventListener("seeked", sincronizar);
    };
  }, [principal, entero, background]);

  useEffect(() => {
    const video = principal.current;
    if (video && seekTo !== undefined && Number.isFinite(seekTo)) {
      video.currentTime = seekTo;
    }
  }, [seekTo, principal]);

  const fondoPlano =
    background === "color"
      ? { background: backgroundColor }
      : background === "gradient"
        ? {
            background: `radial-gradient(120% 80% at 50% 40%, ${backgroundColor}cc, ${backgroundColor})`,
          }
        : undefined;

  return (
    <div className="preview" style={{ aspectRatio: String(ratioValue(aspectRatio)) }}>
      {entero && background === "blur" && (
        <video
          ref={(nodo) => {
            fondo.current = nodo;
          }}
          className="preview__blur"
          src={src}
          muted
          playsInline
          preload="metadata"
          aria-hidden="true"
        />
      )}

      {entero && background !== "blur" && (
        <div className="preview__flat" style={fondoPlano} aria-hidden="true" />
      )}

      <video
        ref={(nodo) => {
          principal.current = nodo;
        }}
        className={`preview__video${entero ? " is-contained" : " is-cropped"}`}
        src={src}
        playsInline
        preload="metadata"
        onLoadedMetadata={(event) => onDuration?.(event.currentTarget.duration)}
        onTimeUpdate={(event) => onTime?.(event.currentTarget.currentTime)}
      />

      {showGrid && (
        <div className="preview__grid" aria-hidden="true">
          <span className="preview__line preview__line--v" style={{ left: "33.333%" }} />
          <span className="preview__line preview__line--v" style={{ left: "66.666%" }} />
          <span className="preview__line preview__line--h" style={{ top: "33.333%" }} />
          <span className="preview__line preview__line--h" style={{ top: "66.666%" }} />
          <span className="preview__corner preview__corner--tl" />
          <span className="preview__corner preview__corner--tr" />
          <span className="preview__corner preview__corner--bl" />
          <span className="preview__corner preview__corner--br" />
        </div>
      )}
    </div>
  );
}
