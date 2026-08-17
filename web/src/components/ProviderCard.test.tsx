import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProviderCard } from "./ProviderCard";
import { mockApi, openOptions, pickOption, renderApp } from "../test/render";
import type { AiProvider } from "../types/api";

const OPENAI: AiProvider = {
  id: "openai",
  label: "OpenAI",
  configured: false,
  masked_key: null,
  key_source: null,
  env_var: "OPENAI_API_KEY",
  testable: true,
  model: "gpt-4o-mini",
  suggested_models: ["gpt-4o-mini", "gpt-4o"],
};

const CONFIGURED: AiProvider = {
  ...OPENAI,
  configured: true,
  masked_key: "sk-•••••••••••••4F2A",
  key_source: "app",
};

const KEY = "sk-test-0000000000000000000000004F2A";

function renderCard(provider: AiProvider, isDefault = false) {
  return renderApp(
    <ProviderCard provider={provider} isDefault={isDefault} onMakeDefault={() => {}} />,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("Configuración de un proveedor de IA", () => {
  it("la clave se escribe oculta y se puede revelar a pedido", async () => {
    mockApi({});
    renderCard(OPENAI);

    const input = screen.getByLabelText("API key");
    expect(input).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: "Mostrar la clave" }));
    expect(screen.getByLabelText("API key")).toHaveAttribute("type", "text");
  });

  it("guarda la clave y deja el campo vacío", async () => {
    const { calls } = mockApi({ "/api/settings/ai/openai/key": { providers: [] } });
    renderCard(OPENAI);

    await userEvent.type(screen.getByLabelText("API key"), KEY);
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardamos la clave.")).toBeInTheDocument();
    expect(screen.getByLabelText("API key")).toHaveValue("");

    const put = calls.find((call) => call.init?.method === "PUT");
    expect(JSON.parse(String(put?.init?.body)).api_key).toBe(KEY);
  });

  it("con la clave guardada muestra solo la versión enmascarada", () => {
    mockApi({});
    renderCard(CONFIGURED);

    expect(screen.getByText(/sk-•+4F2A/)).toBeInTheDocument();
    expect(screen.queryByText(KEY)).not.toBeInTheDocument();
  });

  it("no deja probar la conexión sin haber guardado una clave", async () => {
    mockApi({
      "/api/settings/ai/openai/test": {
        __error: {
          code: "missing_credential",
          message: "Todavía no configuraste la API key de OpenAI.",
        },
      },
    });
    renderCard(OPENAI);

    await userEvent.click(screen.getByRole("button", { name: "Probar conexión" }));

    expect(
      await screen.findByText("Todavía no configuraste la API key de OpenAI."),
    ).toBeInTheDocument();
  });

  it("informa el resultado de una prueba exitosa", async () => {
    mockApi({
      "/api/settings/ai/openai/test": {
        ok: true,
        message: "Conectamos con OpenAI. El modelo «gpt-4o-mini» está disponible.",
        models: ["gpt-4o-mini"],
      },
    });
    renderCard(CONFIGURED);

    await userEvent.click(screen.getByRole("button", { name: "Probar conexión" }));

    expect(await screen.findByText(/Conectamos con OpenAI/)).toBeInTheDocument();
  });

  it("traduce una clave rechazada en vez de mostrar un error crudo", async () => {
    mockApi({
      "/api/settings/ai/openai/test": {
        status: 502,
        __error: {
          code: "provider_auth_error",
          message: "OpenAI rechazó la API key configurada.",
        },
      },
    });
    renderCard(CONFIGURED);

    await userEvent.click(screen.getByRole("button", { name: "Probar conexión" }));

    expect(await screen.findByText("OpenAI rechazó la API key configurada.")).toBeInTheDocument();
  });

  it("actualiza la lista de modelos cuando se lo pedís", async () => {
    mockApi({
      "/api/settings/ai/openai/models": { models: ["gpt-4o-mini", "gpt-4.1", "o3-mini"] },
    });
    renderCard(CONFIGURED);

    await userEvent.click(screen.getByRole("button", { name: "Actualizar modelos" }));

    expect(await screen.findByText(/Encontramos 3 modelos/)).toBeInTheDocument();

    openOptions("Modelo");
    expect(await screen.findByText("o3-mini")).toBeInTheDocument();
  });

  it("permite escribir un modelo que no está en la lista", async () => {
    const { calls } = mockApi({ "/api/settings": { settings: {}, sources: {}, options: {} } });
    renderCard(CONFIGURED);

    await pickOption("Modelo", "Otro modelo…");
    await userEvent.clear(screen.getByLabelText("Nombre del modelo"));
    await userEvent.type(screen.getByLabelText("Nombre del modelo"), "gpt-5-nano");
    await userEvent.click(screen.getByRole("button", { name: "Usar este modelo" }));

    const patch = calls.find((call) => call.init?.method === "PATCH");
    expect(JSON.parse(String(patch?.init?.body))).toEqual({
      ai: { openai_model: "gpt-5-nano" },
    });
  });

  it("pide confirmación antes de borrar la clave", async () => {
    mockApi({ "/api/settings/ai/openai/key": { providers: [] } });
    renderCard(CONFIGURED);

    await userEvent.click(screen.getByRole("button", { name: "Eliminar clave" }));

    expect(screen.getByText("¿Eliminar la clave de OpenAI?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eliminar" })).toBeInTheDocument();
  });

  it("no ofrece borrar una clave que vive en el entorno", () => {
    mockApi({});
    renderCard({ ...CONFIGURED, key_source: "env" });

    expect(screen.queryByRole("button", { name: "Eliminar clave" })).not.toBeInTheDocument();
    expect(screen.getByText("viene de OPENAI_API_KEY")).toBeInTheDocument();
  });

  it("MuAPI se guarda pero todavía no se prueba desde acá", () => {
    mockApi({});
    renderCard({
      ...OPENAI,
      id: "muapi",
      label: "MuAPI",
      env_var: "MUAPI_API_KEY",
      testable: false,
      model: undefined,
      suggested_models: undefined,
    });

    expect(screen.getByLabelText("API key")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Probar conexión" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Modelo")).not.toBeInTheDocument();
  });
});
