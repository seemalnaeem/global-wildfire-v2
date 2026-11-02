import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Import shared helpers with '#shared', no duplication.
    alias: { '#shared': path.resolve(__dirname, 'shared/js/index.js') },
  },
  server: {
    host: true,
    port: 5180,
    // In Docker on Windows/macOS, bind-mounted files do not emit native FS events,
    // so Vite's watcher must poll for HMR to fire. Gated on an env flag so plain
    // local dev (native FS events) is unaffected.
    watch: process.env.VITE_USE_POLLING
      ? { usePolling: true, interval: 300 }
      : undefined,
  },
});
