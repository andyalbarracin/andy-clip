import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Las fuentes vienen del paquete, no de un CDN: la aplicación tiene que abrir
// sin internet.
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

import { App } from "./App";
import "./styles/base.css";

const container = document.getElementById("root");
if (!container) throw new Error("No encontramos el nodo #root");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
