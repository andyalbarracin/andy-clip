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
    rollupOptions: {
      output: {
        // Nombres estables, sin hash. En un servidor público el hash sirve para
        // cachear para siempre; acá lo único que lograba era que un index.html
        // guardado por el navegador pidiera archivos que ya no existen y la
        // aplicación apareciera sin estilos. El servidor manda ETag, así que el
        // navegador igual se entera cuando cambian.
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name].[ext]",
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
