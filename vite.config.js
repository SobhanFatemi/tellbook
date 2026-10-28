import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': process.env.DEV_API_TARGET || 'http://127.0.0.1:8080',
      '/media': process.env.DEV_API_TARGET || 'http://127.0.0.1:8080',
    },
  },
})
