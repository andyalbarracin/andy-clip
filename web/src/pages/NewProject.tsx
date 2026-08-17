import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { Button, ErrorNote, Field, Panel } from "../components/ui";
import "./NewProject.css";

const LANGUAGES = [
  { value: "", label: "Detectar automáticamente" },
  { value: "es", label: "Español" },
  { value: "en", label: "Inglés" },
  { value: "pt", label: "Portugués" },
  { value: "it", label: "Italiano" },
  { value: "fr", label: "Francés" },
];

export function NewProject() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [source, setSource] = useState(params.get("source") ?? "");
  const [name, setName] = useState("");
  const [numClips, setNumClips] = useState<number | null>(null);
  const [aspectRatio, setAspectRatio] = useState<string | null>(null);
  const [resolution, setResolution] = useState<string | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.settings(),
  });

  const { data: ai } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: () => api.aiSettings(),
  });

  const muapiReady = ai?.providers.find((p) => p.id === "muapi")?.configured ?? false;
  const defaults = settings?.settings;
  const options = settings?.options;

  const create = useMutation({
    mutationFn: () =>
      api.createProject({
        source: source.trim(),
        name: name.trim() || undefined,
        options: {
          ...(mode ? { mode } : {}),
          ...(numClips ? { num_clips: numClips } : {}),
          ...(aspectRatio ? { aspect_ratio: aspectRatio } : {}),
          ...(resolution ? { resolution } : {}),
          ...(language !== null ? { language: language || null } : {}),
        },
      }),
    onSuccess: (detail) => navigate(`/proyectos/${detail.project.id}`),
    onError: (err: ApiError) => setError(err),
  });

  return (
    <div className="new-project">
      <h1>Procesar video</h1>

      {error && <ErrorNote message={error.message} action={error.action} />}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          setError(null);
          create.mutate();
        }}
      >
        <Panel title="Origen">
          <div className="new-project__grid">
            <Field
              label="Link o archivo"
              htmlFor="source"
              hint="Un link de YouTube, otra URL compatible, o la ruta completa de un video de tu equipo."
            >
              <input
                id="source"
                className="input"
                value={source}
                onChange={(event) => setSource(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=…"
                autoComplete="off"
                spellCheck={false}
                required
              />
            </Field>

            <Field
              label="Nombre del proyecto"
              htmlFor="name"
              hint="Si lo dejás vacío le ponemos la fecha. Después lo podés cambiar."
            >
              <input
                id="name"
                className="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Opcional"
                maxLength={120}
              />
            </Field>
          </div>
        </Panel>

        <Panel title="Opciones">
          <div className="new-project__grid new-project__grid--four">
            <Field label="Cantidad de clips" htmlFor="num-clips">
              <input
                id="num-clips"
                className="input"
                type="number"
                min={1}
                max={options?.max_clips ?? 10}
                value={numClips ?? defaults?.video.num_clips ?? 3}
                onChange={(event) => setNumClips(Number(event.target.value))}
              />
            </Field>

            <Field label="Relación de aspecto" htmlFor="aspect">
              <select
                id="aspect"
                className="select"
                value={aspectRatio ?? defaults?.video.aspect_ratio ?? "9:16"}
                onChange={(event) => setAspectRatio(event.target.value)}
              >
                {(options?.aspect_ratios ?? ["9:16"]).map((ratio) => (
                  <option key={ratio} value={ratio}>
                    {ratio}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Resolución" htmlFor="resolution">
              <select
                id="resolution"
                className="select"
                value={resolution ?? defaults?.video.resolution ?? "720"}
                onChange={(event) => setResolution(event.target.value)}
              >
                {(options?.resolutions ?? ["720"]).map((value) => (
                  <option key={value} value={value}>
                    {value}p
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Idioma del video" htmlFor="language">
              <select
                id="language"
                className="select"
                value={language ?? defaults?.transcription.language ?? ""}
                onChange={(event) => setLanguage(event.target.value)}
              >
                {LANGUAGES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="new-project__mode">
            <Field
              label="Modo"
              htmlFor="mode"
              hint={
                muapiReady
                  ? "Local procesa todo en tu equipo. MuAPI delega el trabajo en un servicio externo."
                  : "MuAPI queda disponible si cargás su API key en Configuración."
              }
            >
              <select
                id="mode"
                className="select"
                value={mode ?? defaults?.mode ?? "local"}
                onChange={(event) => setMode(event.target.value)}
              >
                <option value="local">Local</option>
                <option value="muapi" disabled={!muapiReady}>
                  MuAPI {muapiReady ? "" : "(sin configurar)"}
                </option>
              </select>
            </Field>
          </div>
        </Panel>

        {/* Este texto describe lo que el código hace de verdad: el video se
            queda en el equipo, y lo que viaja al proveedor es la transcripción. */}
        <p className="privacy">
          En modo local, la descarga, la transcripción y la edición del video pasan en
          tu equipo. Para detectar los mejores momentos le mandamos la transcripción en
          texto al proveedor de IA que hayas configurado. El video no sale de tu
          computadora.
        </p>

        <div className="new-project__submit">
          <Button
            variant="primary"
            type="submit"
            loading={create.isPending}
            disabled={!source.trim()}
          >
            Crear proyecto
          </Button>
        </div>
      </form>
    </div>
  );
}
