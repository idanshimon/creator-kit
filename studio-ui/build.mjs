// esbuild build: bundles src/main.tsx -> dist/app.js + dist/app.css, copies index.html.
// Produces a static dist/ served same-origin by the parent Python server (localhost:4318).
// No Next server, no dev server — just a static bundle.
import { build, context } from 'esbuild';
import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, 'dist');
const watch = process.argv.includes('--watch');

const options = {
  entryPoints: [path.join(root, 'src/main.tsx')],
  bundle: true,
  format: 'esm',
  target: ['es2020'],
  jsx: 'automatic',
  sourcemap: true,
  minify: !watch,
  outdir: dist,
  entryNames: 'app',
  assetNames: '[name]',
  loader: { '.css': 'css' },
  logLevel: 'info',
  define: { 'process.env.NODE_ENV': JSON.stringify(watch ? 'development' : 'production') },
};

async function copyStatic() {
  await mkdir(dist, { recursive: true });
  await cp(path.join(root, 'public'), dist, { recursive: true });
}

if (watch) {
  await copyStatic();
  const ctx = await context(options);
  await ctx.watch();
  console.log('watching…');
} else {
  await copyStatic();
  await build(options);
  // sanity: confirm outputs exist
  for (const f of ['index.html', 'app.js', 'app.css']) {
    await readFile(path.join(dist, f)).catch(() => {
      throw new Error(`Missing expected output dist/${f}`);
    });
  }
  console.log('built dist/ (index.html, app.js, app.css)');
}
