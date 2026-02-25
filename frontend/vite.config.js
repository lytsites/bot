import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Vite v6 expects `true` (allow all) or an array of hosts.
    // Using a string like "all" will not work and results in "Blocked request" errors.
    allowedHosts: true,
  },
  preview: {
    // Keep the same behavior for `vite preview` if you ever use it.
    allowedHosts: true,
  },
})
