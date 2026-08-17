import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("cliente de la API", () => {
  it("muestra el mensaje que escribió el backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 400,
        json: async () => ({
          error: {
            code: "missing_credential",
            message: "Todavía no configuraste la API key de OpenAI.",
            action: "settings/ai",
          },
        }),
      })),
    );

    const error: ApiError = await api.home().then(
      () => {
        throw new Error("esperábamos un error");
      },
      (err) => err as ApiError,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Todavía no configuraste la API key de OpenAI.");
    expect(error.code).toBe("missing_credential");
    expect(error.action).toBe("settings/ai");
  });

  it("explica cuando el backend local no responde", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    const error: ApiError = await api.home().then(
      () => {
        throw new Error("esperábamos un error");
      },
      (err) => err as ApiError,
    );

    expect(error.code).toBe("network_error");
    expect(error.message).toContain("servidor local");
  });

  it("nunca manda la API key por la URL", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }));
    vi.stubGlobal("fetch", fetchMock);

    await api.saveApiKey("openai", "sk-secreta-1234");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).not.toContain("sk-secreta");
    expect(init.method).toBe("PUT");
    expect(init.body).toContain("sk-secreta");
  });
});
