// Port 3003 (architecture D3). API calls under /api are proxied to the backend on 8003, so
// the browser talks to one origin and no CORS configuration is needed in development. The
// frontend is display only: every figure comes from the backend API.
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1', // never 0.0.0.0: the dev server is for this machine only
    port: 3003,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8003',
    },
  },
})
