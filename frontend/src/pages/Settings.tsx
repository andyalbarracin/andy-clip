import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { ErrorNote, Field, Panel } from "../components/ui";
import "./Settings.css";

/** De dónde salió el valor que estás viendo. */
function Source({ source }: { source?: "app" | "env" | "default" }) {
  if (source !== "env") return null;
  return (
    <span className="source-tag" title="Definido por una variable de entorno">
      viene del entorno
    </span>
  );
}

export function Settings() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.settings(),
  });

  const update = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api.updateSettings(patch),
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      window.setTimeout(() => setSaved(false), 2000);
    },
    onError: (err: ApiError) => setError(err),
  });

  if (isLoading || !data) return <p className="muted">Cargando…</p>;

  const { settings, sources, options } = data;
  const save = (patch: Record<string, unknown>) => update.mutate(patch);

  return (
    <div className="settings">
      <div className="settings__head">
        <h1>Configuración</h1>
        {saved && <span className="settings__saved">Guardado</span>}
      </div>

      {error && <ErrorNote message={error.message} action={error.action} />}

      <Panel title="Video">
        <div className="settings__grid">
          <Field
            label="Relación de aspecto predeterminada"
            htmlFor="cfg-aspect"
            hint={<Source source={sources["video.aspect_ratio"]} />}
          >
            <select
              id="cfg-aspect"
              className="select"
              value={settings.video.aspect_ratio}
              onChange={(event) => save({ video: { aspect_ratio: event.target.value } })}
            >
              {options.aspect_ratios.map((ratio) => (
                <option key={ratio} value={ratio}>
                  {ratio}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Cantidad de clips"
            htmlFor="cfg-clips"
            hint={<Source source={sources["video.num_clips"]} />}
          >
            <input
              id="cfg-clips"
              className="input"
              type="number"
              min={1}
              max={options.max_clips}
              defaultValue={settings.video.num_clips}
              onBlur={(event) => save({ video: { num_clips: Number(event.target.value) } })}
            />
          </Field>

          <Field
            label="Resolución"
            htmlFor="cfg-resolution"
            hint={<Source source={sources["video.resolution"]} />}
          >
            <select
              id="cfg-resolution"
              className="select"
              value={settings.video.resolution}
              onChange={(event) => save({ video: { resolution: event.target.value } })}
            >
              {options.resolutions.map((value) => (
                <option key={value} value={value}>
                  {value}p
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Carpeta de resultados"
            htmlFor="cfg-output"
            hint="Relativa a la carpeta del proyecto."
          >
            <input
              id="cfg-output"
              className="input"
              defaultValue={settings.video.output_dir}
              onBlur={(event) => save({ video: { output_dir: event.target.value } })}
            />
          </Field>
        </div>
      </Panel>

      <Panel title="Transcripción">
        <div className="settings__grid">
          <Field
            label="Modelo de Whisper"
            htmlFor="cfg-whisper"
            hint="Los modelos más grandes transcriben mejor y tardan más. Si todavía no lo usaste, se descarga la primera vez."
          >
            <select
              id="cfg-whisper"
              className="select"
              value={settings.transcription.whisper_model}
              onChange={(event) =>
                save({ transcription: { whisper_model: event.target.value } })
              }
            >
              {options.whisper_models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Dispositivo"
            htmlFor="cfg-device"
            hint="Si elegís CUDA y no está disponible, seguimos en CPU."
          >
            <select
              id="cfg-device"
              className="select"
              value={settings.transcription.device}
              onChange={(event) => save({ transcription: { device: event.target.value } })}
            >
              {options.whisper_devices.map((device) => (
                <option key={device} value={device}>
                  {device === "auto" ? "Automático" : device.toUpperCase()}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Detección de voz (VAD)"
            htmlFor="cfg-vad"
            hint="Saltea los silencios. Puede cortar de más en videos con música."
          >
            <select
              id="cfg-vad"
              className="select"
              value={settings.transcription.vad_filter ? "si" : "no"}
              onChange={(event) =>
                save({ transcription: { vad_filter: event.target.value === "si" } })
              }
            >
              <option value="no">Desactivada</option>
              <option value="si">Activada</option>
            </select>
          </Field>
        </div>
      </Panel>

      <Panel title="Sistema">
        <p className="muted small">
          Revisá qué hay instalado en este equipo y qué le falta a Andy Clip para
          procesar un video.
        </p>
        <Link className="btn btn--sm" to="/configuracion/diagnostico">
          Ver diagnóstico
        </Link>
      </Panel>
    </div>
  );
}
