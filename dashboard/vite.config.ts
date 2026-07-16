import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vitest/config'

// Dev mode proxies API calls to the middleware on :8000 (FR-ING-1); in
// production the middleware serves the built SPA itself (NFR-7), so the
// client always talks same-origin and needs no CORS.
const MIDDLEWARE = 'http://127.0.0.1:8000'
const API_PATHS = [
  '/health',
  '/studies',
  '/sessions',
  '/tasks',
  '/findings',
  '/ingest',
  '/files',
  '/requirements',
  '/glossary',
]

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: Object.fromEntries(API_PATHS.map((p) => [p, MIDDLEWARE])),
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
})
