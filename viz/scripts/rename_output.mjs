#!/usr/bin/env node
// Renames the freshly-built single-file HTML in dist to
// `template.html`, verifies the placeholder is intact, and copies it into
// the Python package's ship location.
//
// Args:
//   node rename_output.mjs starmap      # default — ships starmap to gaia/cli/starmap_assets/
//
// The starmap target preserves the original behavior (placeholder
// `__GRAPH_DATA__`, source dir `dist/`, source file `index.html`).
import {
  existsSync,
  renameSync,
  readFileSync,
  statSync,
  unlinkSync,
  copyFileSync,
  mkdirSync,
} from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const TARGETS = {
  starmap: {
    distDir: resolve(__dirname, '..', 'dist'),
    sourceName: 'index.html',
    placeholder: '<!--__GRAPH_DATA__-->',
    shipDir: resolve(__dirname, '..', '..', 'gaia', 'cli', 'starmap_assets'),
  },
};

const which = process.argv[2] ?? 'starmap';
const target = TARGETS[which];
if (!target) {
  console.error(`[rename] unknown target ${which}; expected one of: ${Object.keys(TARGETS).join(', ')}`);
  process.exit(2);
}

const src = resolve(target.distDir, target.sourceName);
const dst = resolve(target.distDir, 'template.html');

if (!existsSync(src)) {
  console.error(`[rename:${which}] expected ${src} to exist`);
  process.exit(1);
}

if (existsSync(dst)) unlinkSync(dst);
renameSync(src, dst);

const html = readFileSync(dst, 'utf-8');
if (!html.includes(target.placeholder)) {
  console.error(
    `[rename:${which}] FAIL: placeholder ${target.placeholder} missing from built HTML`
  );
  process.exit(1);
}

const size = statSync(dst).size;
const sizeKb = (size / 1024).toFixed(1);
console.log(`[rename:${which}] template.html ready (${sizeKb} KB, placeholder OK)`);

mkdirSync(target.shipDir, { recursive: true });
const shipPath = resolve(target.shipDir, 'template.html');
copyFileSync(dst, shipPath);
console.log(`[rename:${which}] copied to ${shipPath}`);
