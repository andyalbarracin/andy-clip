import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Atlassian Design System: reset y tema oscuro.
import "@atlaskit/css-reset";
import { setGlobalTheme } from "@atlaskit/tokens/set-global-theme";

// Las fuentes vienen del paquete, no de un CDN: la aplicación tiene que abrir
// sin internet.
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

import { App } from "./App";
import "./styles/base.css";

// Oscuro y sin alternador: es una herramienta de video, y un fondo claro
// cambia cómo se percibe el clip que estás juzgando.
void setGlobalTheme({ colorMode: "dark", dark: "dark", spacing: "spacing" });

const container = document.getElementById("root");
if (!container) throw new Error("No encontramos el nodo #root");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
