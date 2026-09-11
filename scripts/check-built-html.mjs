#!/usr/bin/env node
/**
 * check-built-html — runs after `next build`. rehype-katex renders TeX it
 * cannot parse as <span class="katex-error" title="...">, and the build
 * succeeds anyway; this fails the build instead if any prerendered page
 * contains one. Honors NEXT_DIST_DIR like next.config.ts.
 *
 *   node scripts/check-built-html.mjs
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const distDir = process.env.NEXT_DIST_DIR || '.next';
const serverApp = join(root, distDir, 'server', 'app');

function htmlFiles(dir, out = []) {
  for (const d of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, d.name);
    if (d.isDirectory()) htmlFiles(full, out);
    else if (d.name.endsWith('.html')) out.push(full);
  }
  return out;
}

if (!existsSync(serverApp)) {
  console.error(`check-built-html: ${relative(root, serverApp)} not found; run next build first.`);
  process.exit(1);
}
const files = htmlFiles(serverApp);
if (!files.length) {
  console.error(`check-built-html: no prerendered HTML under ${relative(root, serverApp)}; the check cannot run.`);
  process.exit(1);
}

const bad = [];
for (const file of files) {
  const html = readFileSync(file, 'utf8');
  if (!html.includes('katex-error')) continue;
  const titles = [...html.matchAll(/class="katex-error"[^>]*title="([^"]*)"/g)].map((m) => m[1]);
  bad.push({ file: relative(root, file).split('\\').join('/'), titles });
}

if (bad.length) {
  for (const b of bad) {
    console.error(`check-built-html: ERROR  ${b.file}: KaTeX error${b.titles.length ? `: ${b.titles.slice(0, 3).join(' | ')}` : ''}`);
  }
  process.exit(1);
}
console.log(`check-built-html: ${files.length} prerendered page(s), no katex-error.`);
