import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";

import { api, ApiError } from "../lib/api";
import { Button } from "./ui";
import "./FilePicker.css";

const ACCEPT = ".mp4,.mov,.mkv,.webm,.m4v,.avi,.mp3,.wav,.m4a,.aac,.flac";

/**
 * Elegir un video del equipo con el selector del sistema.
 *
 * El archivo se copia a la carpeta de la aplicación y devolvemos su ruta, que
 * es lo que el motor necesita. Un video local se salta la descarga entera, así
 * que no hay plataforma que pueda bloquearlo.
 */
export function FilePicker({
  onPicked,
  onError,
}: {
  onPicked: (path: string, name: string) => void;
  onError?: (message: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadVideo(file),
    onSuccess: (data) => onPicked(data.path, data.name),
    onError: (error: ApiError) => onError?.(error.message),
  });

  return (
    <span className="picker">
      <input
        ref={input}
        className="sr-only"
        type="file"
        accept={ACCEPT}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) upload.mutate(file);
          // Permite volver a elegir el mismo archivo si hizo falta reintentar.
          event.target.value = "";
        }}
      />
      <Button onClick={() => input.current?.click()} loading={upload.isPending}>
        {upload.isPending ? "Copiando…" : "Elegir archivo"}
      </Button>
    </span>
  );
}
