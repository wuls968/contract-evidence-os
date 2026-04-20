import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/auth": "http://127.0.0.1:8080",
      "/ui": "http://127.0.0.1:8080",
      "/config": "http://127.0.0.1:8080",
      "/usage": "http://127.0.0.1:8080",
      "/events": "http://127.0.0.1:8080",
      "/v1": "http://127.0.0.1:8080",
      "/metrics": "http://127.0.0.1:8080"
    }
  },
  build: {
    outDir: "dist"
  }
});

