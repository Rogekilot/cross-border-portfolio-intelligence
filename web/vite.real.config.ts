import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/** F1 R7: the real-mode profile. Its own port and its own API target (the real-mode launcher, `src/web_api/real_launcher.py`, default 8004); the other
 * Vite configs and their origins are unchanged. The page is `/real.html`. */
export default defineConfig({
  plugins: [react()],
  envDir: false,
  server: {
    host: '127.0.0.1', port: 5175, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8004', changeOrigin: false } },
  },
});
