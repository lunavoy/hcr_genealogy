import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5100',
      '/recognize': 'http://127.0.0.1:5100',
      '/detect-layout': 'http://127.0.0.1:5100',
    },
  },
})
