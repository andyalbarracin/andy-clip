/** Formas que devuelve el backend local. */

export type ComponentStatus =
  | "available"
  | "configured"
  | "not_configured"
  | "not_detected"
  | "error";

export interface SystemComponent {
  id: string;
  label: string;
  status: ComponentStatus;
  version: string | null;
  detail: string | null;
}

export interface LocalModeReadiness {
  ready: boolean;
  missing: string[];
}

export interface Health {
  status: string;
  app: string;
  version: string;
  mode: string;
  local_mode: LocalModeReadiness;
}

export interface ProcessingOptions {
  mode: string;
  num_clips: number;
  aspect_ratio: string;
  resolution: string;
  language: string | null;
  framing: string;
  background: string;
  background_color: string;
}

export interface Project {
  id: string;
  name: string;
  source: string;
  source_type: "url" | "file";
  status: "draft" | "processing" | "done" | "failed" | "cancelled";
  settings: ProcessingOptions;
  transcript: Transcript | null;
  duration: number | null;
  media_path: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  duration: number;
  segments: TranscriptSegment[];
}

export interface Highlight {
  id: string;
  project_id: string;
  position: number;
  title: string;
  start_time: number;
  end_time: number;
  duration: number;
  score: number;
  hook_sentence: string | null;
  virality_reason: string | null;
  selected: boolean;
}

export interface Clip {
  id: string;
  project_id: string;
  highlight_id: string | null;
  position: number;
  path: string | null;
  aspect_ratio: string;
  duration: number | null;
  status: string;
  error: string | null;
  created_at: string;
  project_name?: string;
}

export interface Job {
  id: string;
  project_id: string;
  status: "pending" | "queued" | "processing" | "done" | "failed" | "cancelled";
  status_label: string;
  stage: string | null;
  stage_label: string | null;
  message: string | null;
  progress: number | null;
  error: string | null;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ProjectDetail {
  project: Project;
  highlights: Highlight[];
  clips: Clip[];
  job: Job | null;
}

export interface HomePayload {
  recent_projects: Project[];
  recent_clips: Clip[];
  total_projects: number;
  system: SystemComponent[];
  local_mode: LocalModeReadiness;
}

export interface AppSettings {
  mode: string;
  ai: { provider: string; openai_model: string; gemini_model: string };
  transcription: {
    whisper_model: string;
    device: string;
    vad_filter: boolean;
    language: string | null;
  };
  video: {
    aspect_ratio: string;
    num_clips: number;
    resolution: string;
    output_dir: string;
    framing: string;
    background: string;
    background_color: string;
  };
}

export interface SettingsOptions {
  modes: string[];
  providers: { id: string; label: string }[];
  aspect_ratios: string[];
  resolutions: string[];
  whisper_models: string[];
  whisper_devices: string[];
  max_clips: number;
  framings: { id: string; label: string }[];
  backgrounds: { id: string; label: string }[];
  suggested_models: Record<string, string[]>;
}

export interface SettingsPayload {
  settings: AppSettings;
  sources: Record<string, "app" | "env" | "default">;
  options: SettingsOptions;
  analysis: Record<string, unknown>;
}

export interface AiProvider {
  id: string;
  label: string;
  configured: boolean;
  masked_key: string | null;
  key_source: "app" | "env" | null;
  env_var: string;
  testable: boolean;
  model?: string;
  suggested_models?: string[];
}

export interface AiSettingsPayload {
  default_provider: string;
  providers: AiProvider[];
}
