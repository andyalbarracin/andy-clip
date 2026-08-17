import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

export function renderApp(ui: ReactElement, route = "/") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Respuestas del backend por ruta, para no salir a la red en los tests. */
export function mockApi(routes: Record<string, unknown>) {
  const calls: { url: string; init?: RequestInit }[] = [];

  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const key = Object.keys(routes).find((route) => url.startsWith(route));
    const payload = key ? routes[key] : null;

    if (payload && typeof payload === "object" && "__error" in payload) {
      const error = payload as { __error: { code: string; message: string }; status?: number };
      return {
        ok: false,
        status: error.status ?? 400,
        json: async () => ({ error: error.__error }),
      } as Response;
    }

    return { ok: true, status: 200, json: async () => payload } as Response;
  });

  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}
