import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Same origin for API, websocket and photos, so the SMS link works from a phone on the LAN / tunnel.
    proxy: {
      "/api/v1/ws": { target: API, ws: true },
      "/api": { target: API, changeOrigin: true },
      "/uploads": { target: API, changeOrigin: true },
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: { manualChunks: { map: ["leaflet", "react-leaflet"] } },
    },
  },
});
