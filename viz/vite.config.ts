import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { resolve } from 'node:path';

// Two separate single-file builds share this config; the env var
// VIZ_ENTRY=replay switches the build to the timeline-replay HTML.
// Default (unset / "starmap") builds the existing static starmap.
const entry = process.env.VIZ_ENTRY ?? 'starmap';

const inputs: Record<string, { input: string; outDir: string }> = {
  starmap: {
    input: resolve(__dirname, 'index.html'),
    outDir: 'dist',
  },
  replay: {
    input: resolve(__dirname, 'index-replay.html'),
    outDir: 'dist-replay',
  },
};

const cfg = inputs[entry];
if (!cfg) {
  throw new Error(`unknown VIZ_ENTRY=${JSON.stringify(entry)}; expected starmap | replay`);
}

export default defineConfig({
  plugins: [viteSingleFile()],
  build: {
    target: 'es2020',
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000,
    chunkSizeWarningLimit: 100_000_000,
    outDir: cfg.outDir,
    emptyOutDir: true,
    rollupOptions: {
      input: cfg.input,
      output: {
        inlineDynamicImports: true,
      },
    },
  },
});
