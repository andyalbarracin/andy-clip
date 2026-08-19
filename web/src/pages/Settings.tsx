import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError } from "../lib/api";
import { ButtonLink, Choice, ErrorNote, Field, Panel, TextInput } from "../components/ui";
import { ProviderCard } from "../components/ProviderCard";
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

  const { data: ai } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: () => api.aiSettings(),
  });

  const update = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api.updateSettings(patch),
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      queryClient.invalidateQueries({ queryKey: ["ai-settings"] });
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

      <Panel title="Inteligencia artificial">
        <p className="muted small settings__intro">
          Andy Clip usa un proveedor de IA solo para elegir los mejores momentos a
          partir de la transcripción. Alcanza con configurar uno, pero si cargás
          más de uno y el predeterminado se queda sin saldo o te limita los
          pedidos, el procesamiento sigue con el siguiente en vez de perderse.
        </p>

        {(ai?.providers ?? []).filter((p) => p.testable && p.configured).length > 1 && (
          <p className="muted small settings__intro">
            Orden de respaldo:{" "}
            <strong>
              {[
                ai?.default_provider,
                ...(ai?.providers ?? [])
                  .filter((p) => p.testable && p.configured && p.id !== ai?.default_provider)
                  .map((p) => p.id),
              ]
                .filter(Boolean)
                .join(" → ")}
            </strong>
          </p>
        )}

        {ai?.providers.map((provider) => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            isDefault={ai.default_provider === provider.id}
            onMakeDefault={() => save({ ai: { provider: provider.id } })}
          />
        ))}
      </Panel>

      <Panel title="Video">
        <div className="settings__grid">
          <Field
            label="Relación de aspecto predeterminada"
            htmlFor="cfg-aspect"
            hint={<Source source={sources["video.aspect_ratio"]} />}
          >
            <Choice
              id="cfg-aspect"
              value={settings.video.aspect_ratio}
              onChange={(value) => save({ video: { aspect_ratio: value } })}
              options={options.aspect_ratios.map((ratio) => ({ value: ratio, label: ratio }))}
            />
          </Field>

          <Field
            label="Cantidad de clips"
            htmlFor="cfg-clips"
            hint={<Source source={sources["video.num_clips"]} />}
          >
            <TextInput
              id="cfg-clips"
              type="number"
              min={1}
              max={options.max_clips}
              defaultValue={settings.video.num_clips}
              onBlur={(event: React.FocusEvent<HTMLInputElement>) =>
                save({ video: { num_clips: Number(event.target.value) } })
              }
            />
          </Field>

          <Field
            label="Resolución"
            htmlFor="cfg-resolution"
            hint={<Source source={sources["video.resolution"]} />}
          >
            <Choice
              id="cfg-resolution"
              value={settings.video.resolution}
              onChange={(value) => save({ video: { resolution: value } })}
              options={options.resolutions.map((value) => ({ value, label: `${value}p` }))}
            />
          </Field>

          <Field
            label="Encuadre predeterminado"
            htmlFor="cfg-framing"
            hint={
              settings.video.framing === "fit"
                ? "El video entra entero, sin perder zócalos ni subtítulos quemados."
                : "Recorta a vertical: lo que quede fuera del cuadro se pierde."
            }
          >
            <Choice
              id="cfg-framing"
              value={settings.video.framing}
              onChange={(value) => save({ video: { framing: value } })}
              options={options.framings.map((item) => ({ value: item.id, label: item.label }))}
            />
          </Field>

          {settings.video.framing === "fit" && (
            <Field label="Relleno de arriba y abajo" htmlFor="cfg-background">
              <Choice
                id="cfg-background"
                value={settings.video.background}
                onChange={(value) => save({ video: { background: value } })}
                options={options.backgrounds.map((item) => ({ value: item.id, label: item.label }))}
              />
            </Field>
          )}

          {settings.video.framing === "fit" && settings.video.background === "color" && (
            <Field label="Color del relleno" htmlFor="cfg-bgcolor">
              <TextInput
                id="cfg-bgcolor"
                type="color"
                defaultValue={settings.video.background_color}
                onBlur={(event: React.FocusEvent<HTMLInputElement>) =>
                  save({ video: { background_color: event.target.value.toUpperCase() } })
                }
              />
            </Field>
          )}

          <Field
            label="Carpeta de resultados"
            htmlFor="cfg-output"
            hint="Relativa a la carpeta del proyecto."
          >
            <TextInput
              id="cfg-output"
              defaultValue={settings.video.output_dir}
              onBlur={(event: React.FocusEvent<HTMLInputElement>) =>
                save({ video: { output_dir: event.target.value } })
              }
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
            <Choice
              id="cfg-whisper"
              value={settings.transcription.whisper_model}
              onChange={(value) => save({ transcription: { whisper_model: value } })}
              options={options.whisper_models.map((model) => ({ value: model, label: model }))}
            />
          </Field>

          <Field
            label="Dispositivo"
            htmlFor="cfg-device"
            hint="Si elegís CUDA y no está disponible, seguimos en CPU."
          >
            <Choice
              id="cfg-device"
              value={settings.transcription.device}
              onChange={(value) => save({ transcription: { device: value } })}
              options={options.whisper_devices.map((device) => ({
                value: device,
                label: device === "auto" ? "Automático" : device.toUpperCase(),
              }))}
            />
          </Field>

          <Field
            label="Detección de voz (VAD)"
            htmlFor="cfg-vad"
            hint="Saltea los silencios. Puede cortar de más en videos con música."
          >
            <Choice
              id="cfg-vad"
              value={settings.transcription.vad_filter ? "si" : "no"}
              onChange={(value) => save({ transcription: { vad_filter: value === "si" } })}
              options={[
                { value: "no", label: "Desactivada" },
                { value: "si", label: "Activada" },
              ]}
            />
          </Field>
        </div>
      </Panel>

      <Panel title="Sistema">
        <p className="muted small">
          Revisá qué hay instalado en este equipo y qué le falta a Andy Clip para
          procesar un video.
        </p>
        <ButtonLink to="/configuracion/diagnostico" size="sm">
          Ver diagnóstico
        </ButtonLink>
      </Panel>
    </div>
  );
}
