import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { Diagnostics } from "./pages/Diagnostics";
import { Home } from "./pages/Home";
import { NewProject } from "./pages/NewProject";
import { ProjectDetail } from "./pages/ProjectDetail";
import { Projects } from "./pages/Projects";
import { Settings } from "./pages/Settings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Es una aplicación local: los datos llegan rápido y no hay razón para
      // reintentar contra un backend que está en la misma máquina.
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Home />} />
            <Route path="proyectos" element={<Projects />} />
            <Route path="proyectos/:id" element={<ProjectDetail />} />
            <Route path="procesar" element={<NewProject />} />
            <Route path="configuracion" element={<Settings />} />
            <Route path="configuracion/diagnostico" element={<Diagnostics />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
