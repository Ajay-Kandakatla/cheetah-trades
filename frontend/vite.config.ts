import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/stream': { target: 'http://localhost:8000', changeOrigin: true },
      '/snapshot': { target: 'http://localhost:8000', changeOrigin: true },
      '/cheetah': { target: 'http://localhost:8000', changeOrigin: true },
      '/competitors': { target: 'http://localhost:8000', changeOrigin: true },
      '/unicorns': { target: 'http://localhost:8000', changeOrigin: true },
      '/etfs': { target: 'http://localhost:8000', changeOrigin: true },
      '/news': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/indian-stocks': { target: 'http://localhost:8000', changeOrigin: true },
      '/indian-news': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
