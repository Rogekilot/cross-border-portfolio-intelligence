import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/** Explicit new local profile. The legacy Vite config and all existing origins remain unchanged. */
export default defineConfig({
  plugins: [react()],
  envDir: false,
  server: {
    host: '127.0.0.1', port: 5174, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8003', changeOrigin: false } },
  },
});
