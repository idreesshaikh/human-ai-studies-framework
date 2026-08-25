import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// The middleware (port 8000) owns the API and serves this app in
// production; Vite is only used in dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    /* Keep the browser's same-origin API contract in development. Without this
     * proxy, a POST from the form lands on Vite and returns its plain 404 page,
     * which makes the product look like the compiler failed. */
    proxy: {
      "/analysis": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/corpus": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/ingest": "http://127.0.0.1:8000",
      "/me": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/studies": "http://127.0.0.1:8000",
      "/templates": "http://127.0.0.1:8000",
    },
  },
});
