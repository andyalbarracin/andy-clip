import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// El backend vive en 127.0.0.1:8756. En desarrollo el proxy evita tener que
// pensar en CORS y hace que el frontend hable siempre contra rutas /api.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8756",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
