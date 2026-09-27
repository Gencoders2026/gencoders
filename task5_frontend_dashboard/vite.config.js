import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/session': 'http://127.0.0.1:8080',
      '/sessions': 'http://127.0.0.1:8080',
      '/analyze': 'http://127.0.0.1:8080',
      '/support': 'http://127.0.0.1:8080',
      '/coaching': 'http://127.0.0.1:8080',
      '/escalation': 'http://127.0.0.1:8080',
      '/config': 'http://127.0.0.1:8080',
      '/health': 'http://127.0.0.1:8080',
    }
  }
})
