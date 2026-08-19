import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../lib/api";
import { Button, Choice, ErrorNote, Field, Panel, TextInput } from "../components/ui";
import { FilePicker } from "../components/FilePicker";
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
  const [pickedName, setPickedName] = useState<string | null>(null);
  const [numClips, setNumClips] = useState<number | null>(null);
  const [aspectRatio, setAspectRatio] = useState<string | null>(null);
  const [resolution, setResolution] = useState<string | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [framing, setFraming] = useState<string | null>(null);
  const [background, setBackground] = useState<string | null>(null);
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
          ...(framing ? { framing } : {}),
          ...(background ? { background } : {}),
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
              hint={
                pickedName
                  ? `Vas a procesar «${pickedName}», que ya está en tu equipo.`
                  : "Pegá un link de YouTube, o elegí un video de tu equipo. Un archivo local se salta la descarga."
              }
            >
              <div className="new-project__source">
                <TextInput
                  id="source"
                  value={source}
                  onChange={(value) => {
                    setSource(value);
                    setPickedName(null);
                  }}
                  placeholder="https://www.youtube.com/watch?v=…"
                  isRequired
                />
                <FilePicker
                  onPicked={(path, name) => {
                    setSource(path);
                    setPickedName(name);
                    setError(null);
                  }}
                  onError={(message) =>
                    setError(new ApiError(message, "upload_failed", 400))
                  }
                />
              </div>
            </Field>

            <Field
              label="Nombre del proyecto"
              htmlFor="name"
              hint="Si lo dejás vacío le ponemos la fecha. Después lo podés cambiar."
            >
              <TextInput
                id="name"
                value={name}
                onChange={setName}
                placeholder="Opcional"
                maxLength={120}
              />
            </Field>
          </div>
        </Panel>

        <Panel title="Opciones">
          <div className="new-project__grid new-project__grid--four">
            <Field label="Cantidad de clips" htmlFor="num-clips">
              <TextInput
                id="num-clips"
                type="number"
                min={1}
                max={options?.max_clips ?? 10}
                value={numClips ?? defaults?.video.num_clips ?? 3}
                onChange={(value) => setNumClips(Number(value))}
              />
            </Field>

            <Field label="Relación de aspecto" htmlFor="aspect">
              <Choice
                id="aspect"
                value={aspectRatio ?? defaults?.video.aspect_ratio ?? "9:16"}
                onChange={setAspectRatio}
                options={(options?.aspect_ratios ?? ["9:16"]).map((ratio) => ({
                  value: ratio,
                  label: ratio,
                }))}
              />
            </Field>

            <Field label="Resolución" htmlFor="resolution">
              <Choice
                id="resolution"
                value={resolution ?? defaults?.video.resolution ?? "720"}
                onChange={setResolution}
                options={(options?.resolutions ?? ["720"]).map((value) => ({
                  value,
                  label: `${value}p`,
                }))}
              />
            </Field>

            <Field label="Idioma del video" htmlFor="language">
              <Choice
                id="language"
                value={language ?? defaults?.transcription.language ?? ""}
                onChange={setLanguage}
                options={LANGUAGES}
              />
            </Field>
          </div>

          <div className="new-project__grid new-project__grid--four">
            <Field
              label="Encuadre"
              htmlFor="framing"
              hint={
                (framing ?? defaults?.video.framing) === "fit"
                  ? "El video entra entero: no se pierden zócalos ni subtítulos quemados."
                  : "Recorta a vertical. Lo que quede fuera del cuadro se pierde."
              }
            >
              <Choice
                id="framing"
                value={framing ?? defaults?.video.framing ?? "faces"}
                onChange={setFraming}
                options={(options?.framings ?? []).map((item) => ({
                  value: item.id,
                  label: item.label,
                }))}
              />
            </Field>

            {(framing ?? defaults?.video.framing) === "fit" && (
              <Field label="Relleno de arriba y abajo" htmlFor="background">
                <Choice
                  id="background"
                  value={background ?? defaults?.video.background ?? "blur"}
                  onChange={setBackground}
                  options={(options?.backgrounds ?? []).map((item) => ({
                    value: item.id,
                    label: item.label,
                  }))}
                />
              </Field>
            )}
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
              <Choice
                id="mode"
                value={mode ?? defaults?.mode ?? "local"}
                onChange={setMode}
                options={[
                  { value: "local", label: "Local" },
                  {
                    value: "muapi",
                    label: muapiReady ? "MuAPI" : "MuAPI (sin configurar)",
                    isDisabled: !muapiReady,
                  },
                ]}
              />
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
