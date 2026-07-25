import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
        port: 5173,
        proxy: {
            "/api": { target: "http://localhost:8000", changeOrigin: true },
            "/health": { target: "http://localhost:8000", changeOrigin: true },
            // Run event stream (Django Channels). Without this the dev page opens
            // ws://localhost:5173/ws/... — unproxied, so the live stream never connects
            // and just retries forever. Production is covered by frontend/nginx.conf.
            "/ws": { target: "ws://localhost:8000", ws: true, changeOrigin: true },
        },
    },
});
