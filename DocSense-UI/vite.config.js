import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The DocSense backend runs separately: `uvicorn api.main:app --port 8000` from the DocSense project root.
// The UI calls /api/... on its own origin and Vite forwards each request to the backend with the /api
// prefix removed, so the backend needs no CORS change. Set DOCSENSE_API_URL to use another address.
const apiProxy = {
  '/api/': {
    target: process.env.DOCSENSE_API_URL || 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
});
