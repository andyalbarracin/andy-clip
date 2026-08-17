import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NewProject } from "./NewProject";
import { mockApi, renderApp } from "../test/render";

const SETTINGS = {
  settings: {
    mode: "local",
    ai: { provider: "openai", openai_model: "gpt-4o-mini", gemini_model: "gemini-2.5-flash" },
    transcription: { whisper_model: "base", device: "auto", vad_filter: false, language: null },
    video: { aspect_ratio: "9:16", num_clips: 3, resolution: "720", output_dir: "output" },
  },
  sources: {},
  options: {
    modes: ["local", "muapi"],
    providers: [{ id: "openai", label: "OpenAI" }],
    aspect_ratios: ["9:16", "1:1", "4:5"],
    resolutions: ["360", "480", "720", "1080"],
    whisper_models: ["tiny", "base"],
    whisper_devices: ["auto", "cpu"],
    max_clips: 10,
    suggested_models: {},
  },
  analysis: {},
};

const AI = {
  default_provider: "openai",
  providers: [{ id: "muapi", label: "MuAPI", configured: false, testable: false }],
};

afterEach(() => vi.unstubAllGlobals());

describe("Procesar video", () => {
  it("arranca con los valores de la configuración global", async () => {
    mockApi({ "/api/settings/ai": AI, "/api/settings": SETTINGS });

    renderApp(<NewProject />);

    // Esperamos a que lleguen las opciones del backend, no al valor por
    // defecto — coinciden, y el test pasaría sin haber cargado nada.
    await screen.findByRole("option", { name: "4:5" });

    expect(screen.getByLabelText("Cantidad de clips")).toHaveValue(3);
    expect(screen.getByLabelText("Relación de aspecto")).toHaveValue("9:16");
    expect(screen.getByLabelText("Resolución")).toHaveValue("720");
  });

  it("toma la fuente que viene del Inicio", async () => {
    mockApi({ "/api/settings/ai": AI, "/api/settings": SETTINGS });

    renderApp(<NewProject />, "/procesar?source=https%3A%2F%2Fyoutu.be%2Fabc");

    expect(screen.getByLabelText("Link o archivo")).toHaveValue("https://youtu.be/abc");
  });

  it("manda solo las opciones que se cambiaron", async () => {
    const { calls } = mockApi({
      "/api/settings/ai": AI,
      "/api/settings": SETTINGS,
      "/api/projects": { project: { id: "p1" }, highlights: [], clips: [], job: null },
    });

    renderApp(<NewProject />, "/procesar?source=https%3A%2F%2Fyoutu.be%2Fabc");
    await screen.findByRole("option", { name: "4:5" });

    await userEvent.selectOptions(screen.getByLabelText("Relación de aspecto"), "4:5");
    await userEvent.click(screen.getByRole("button", { name: "Crear proyecto" }));

    await waitFor(() => {
      const post = calls.find((call) => call.init?.method === "POST");
      expect(post).toBeDefined();
      const body = JSON.parse(String(post?.init?.body));
      expect(body.source).toBe("https://youtu.be/abc");
      expect(body.options.aspect_ratio).toBe("4:5");
      expect(body.options.num_clips).toBeUndefined();
    });
  });

  it("muestra el error del backend en vez de un 500 pelado", async () => {
    mockApi({
      "/api/settings/ai": AI,
      "/api/settings": SETTINGS,
      "/api/projects": {
        __error: { code: "invalid_source", message: "No encontramos ese archivo en tu equipo." },
      },
    });

    renderApp(<NewProject />, "/procesar?source=%2Ftmp%2Fno-existe.mp4");
    await screen.findByRole("option", { name: "4:5" });

    await userEvent.click(screen.getByRole("button", { name: "Crear proyecto" }));

    expect(
      await screen.findByText("No encontramos ese archivo en tu equipo."),
    ).toBeInTheDocument();
  });

  it("no deja elegir MuAPI si no está configurado", async () => {
    mockApi({ "/api/settings/ai": AI, "/api/settings": SETTINGS });

    renderApp(<NewProject />);
    await waitFor(() => expect(screen.getByLabelText("Modo")).toBeInTheDocument());

    expect(screen.getByRole("option", { name: /MuAPI/ })).toBeDisabled();
  });
});
