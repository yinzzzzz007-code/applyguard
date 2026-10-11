import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: UI on :5173, proxy API to ApplyGuard backend :8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Evidence import can take a while (decode + parse); avoid premature proxy reset.
        timeout: 180_000,
        proxyTimeout: 180_000,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
