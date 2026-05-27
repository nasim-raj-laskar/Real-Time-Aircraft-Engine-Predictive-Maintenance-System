import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
      '/predict': { target: 'http://localhost:8000', changeOrigin: true },
      '/engines': { target: 'http://localhost:8000', changeOrigin: true },
      '/health':  { target: 'http://localhost:8000', changeOrigin: true },
      '/model':   { target: 'http://localhost:8000', changeOrigin: true },
      '/alerts':  { target: 'http://localhost:8000', changeOrigin: true },
      '/metrics': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
