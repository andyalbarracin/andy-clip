/**
 * Cliente del backend local.
 *
 * El backend siempre contesta los errores con la misma forma
 * `{ error: { code, message, action } }`, donde `message` ya está escrito para
 * mostrarse tal cual. `ApiError` conserva `action` para poder ofrecer el
 * camino de salida ("Ir a configuración") en vez de dejar a la persona en un
 * callejón.
 */
import type {
  AiSettingsPayload,
  HomePayload,
  Job,
  Project,
  ProjectDetail,
  SettingsPayload,
  SystemComponent,
  Transcript,
} from "../types/api";

export class ApiError extends Error {
  readonly code: string;
  readonly action?: string;
  readonly status: number;

  constructor(message: string, code: string, status: number, action?: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.action = action;
  }
}

const GENERIC_MESSAGE =
  "No pudimos comunicarnos con Andy Clip. Fijate que el servidor local esté corriendo.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const isForm = init?.body instanceof FormData;
    response = await fetch(path, {
      ...init,
      headers: init?.body && !isForm ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError(GENERIC_MESSAGE, "network_error", 0);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const error = payload?.error;
    throw new ApiError(
      error?.message ?? GENERIC_MESSAGE,
      error?.code ?? "error",
      response.status,
      error?.action,
    );
  }

  return payload as T;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  home: () => request<HomePayload>("/api/home"),

  systemStatus: () =>
    request<{ components: SystemComponent[] }>("/api/system/status"),

  projects: (limit = 50) =>
    request<{ projects: Project[]; total: number }>(`/api/projects?limit=${limit}`),

  project: (id: string) => request<ProjectDetail>(`/api/projects/${id}`),

  createProject: (body: {
    source: string;
    name?: string;
    options?: Partial<{
      mode: string;
      num_clips: number;
      aspect_ratio: string;
      resolution: string;
      language: string | null;
    }>;
  }) => post<ProjectDetail>("/api/projects", body),

  renameProject: (id: string, name: string) =>
    request<ProjectDetail>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  deleteProject: (id: string) =>
    request<{ deleted: string }>(`/api/projects/${id}`, { method: "DELETE" }),

  transcript: (id: string) => request<Transcript>(`/api/projects/${id}/transcript`),

  processProject: (id: string) => post<{ job: Job }>(`/api/projects/${id}/process`),

  /** Volver a generar los clips con otros ajustes, sin rehacer el análisis. */
  rerenderProject: (
    id: string,
    ajustes: Partial<{
      framing: string;
      background: string;
      background_color: string;
      aspect_ratio: string;
      resolution: string;
    }>,
  ) => post<{ job: Job }>(`/api/projects/${id}/rerender`, ajustes),

  /**
   * Copiar un video del equipo a la carpeta de la aplicación.
   *
   * El navegador no puede entregar la ruta real de un archivo, así que hay que
   * mandarle el contenido al backend. Como corre en la misma máquina, esto es
   * una copia de disco a disco: no sale nada a internet.
   */
  uploadVideo: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    // Sin cabecera Content-Type a propósito: el navegador tiene que ponerla
    // con el separador que genera para el formulario.
    return request<{ path: string; name: string; size: number }>("/api/uploads", {
      method: "POST",
      body,
    });
  },

  stages: () => request<{ stages: { id: string; label: string }[] }>("/api/jobs/stages"),

  job: (id: string) => request<{ job: Job }>(`/api/jobs/${id}`),

  cancelJob: (id: string) => post<{ job: Job }>(`/api/jobs/${id}/cancel`),

  settings: () => request<SettingsPayload>("/api/settings"),

  updateSettings: (patch: Record<string, unknown>) =>
    request<SettingsPayload>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  aiSettings: () => request<AiSettingsPayload>("/api/settings/ai"),

  saveApiKey: (provider: string, apiKey: string) =>
    request<AiSettingsPayload>(`/api/settings/ai/${provider}/key`, {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey }),
    }),

  deleteApiKey: (provider: string) =>
    request<AiSettingsPayload>(`/api/settings/ai/${provider}/key`, { method: "DELETE" }),

  testProvider: (provider: string) =>
    post<{ ok: boolean; message: string; models: string[] }>(
      `/api/settings/ai/${provider}/test`,
    ),

  refreshModels: (provider: string) =>
    post<{ models: string[] }>(`/api/settings/ai/${provider}/models`),

  clipFileUrl: (clipId: string, download = false) =>
    `/api/clips/${clipId}/file${download ? "?download=true" : ""}`,
};
