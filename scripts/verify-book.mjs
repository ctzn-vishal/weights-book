#!/usr/bin/env node
/**
 * verify-book — the build's consistency gate. Runs after gen-registry and
 * before `next build` (see package.json "build"):
 *
 *   node --import tsx scripts/verify-book.mjs
 *
 * (tsx lets it import lib/toc.ts, the single source of truth for the TOC.)
 *
 * (a) TOC and directories
 *     error   an app/ch* or app/appendix-* directory that is not in the TOC
 *     error   a chapter page.tsx that calls chapterPage() with another slug
 *     warn    a TOC entry with no directory or no page file (the placeholder
 *             route serves it; chapters arrive over the course of the draft)
 * (b) data references in every app/**\/article.mdx (including app/dev/**)
 *     error   <Fact>/<KeyNumber>/<Chart>/<Ledger>/<Cite> or widget id that does not resolve
 *     error   <Chart> pointed at widget data, a widget pointed at the wrong figure type
 *     error   <Fact ci> on a fact without ci_display
 *     warn    orphan facts: exported but cited by no article (directly or via a ledger)
 * (c) wiring
 *     error   lib/site.ts BASE_PATH differs from next.config.ts basePath
 *     error   a global component missing from mdx-components.tsx
 *
 * Exit 1 on any error. Warnings print and pass.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CHART_TYPES, GLOBAL_COMPONENTS, WIDGET_DATA, blankNonProse, lineAt, scanReferences } from './lib/book-contract.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const appDir = join(root, 'app');
const rel = (p) => relative(root, p).split('\\').join('/');
const errors = [];
const warnings = [];

let toc;
try {
  toc = await import('../lib/toc.ts');
} catch (e) {
  console.error(`verify-book: cannot import lib/toc.ts (${e.message}). Run with: node --import tsx scripts/verify-book.mjs`);
  process.exit(1);
}

// ------------------------------------------------------------------ (a) TOC and directories
const PAGE_FILES = ['page.tsx', 'page.ts', 'page.jsx', 'page.js', 'page.mdx', 'page.md'];
const entries = toc.allEntries;
const slugs = new Set();
const keys = new Set();
for (const e of entries) {
  if (slugs.has(e.slug)) errors.push(`lib/toc.ts: duplicate slug "${e.slug}"`);
  if (keys.has(e.key)) errors.push(`lib/toc.ts: duplicate key "${e.key}"`);
  slugs.add(e.slug);
  keys.add(e.key);
}

const chapterDirs = readdirSync(appDir, { withFileTypes: true })
  .filter((d) => d.isDirectory() && /^(ch\d|appendix-)/.test(d.name))
  .map((d) => d.name);
for (const d of chapterDirs) {
  if (!slugs.has(d)) errors.push(`app/${d}/ is not in lib/toc.ts (orphaned or misnamed directory)`);
}

let placeholders = 0;
for (const e of entries) {
  const dir = join(appDir, e.slug);
  if (!existsSync(dir)) {
    warnings.push(`${e.slug}: no app/${e.slug}/ yet; the placeholder page is served`);
    placeholders++;
    continue;
  }
  if (!PAGE_FILES.some((f) => existsSync(join(dir, f)))) {
    warnings.push(`app/${e.slug}/ has no page file; the placeholder page is served`);
    placeholders++;
    continue;
  }
  if (!existsSync(join(dir, 'article.mdx'))) warnings.push(`app/${e.slug}/ has a page but no article.mdx`);
  const pagePath = join(dir, 'page.tsx');
  if (existsSync(pagePath)) {
    const m = /chapterPage\(\s*['"]([^'"]+)['"]/.exec(readFileSync(pagePath, 'utf8'));
    if (m && m[1] !== e.slug) errors.push(`app/${e.slug}/page.tsx calls chapterPage('${m[1]}'); expected '${e.slug}'`);
  }
}

// ------------------------------------------------------------------ (b) data references
const registryPath = join(root, 'lib', 'generated', 'registry.json');
if (!existsSync(registryPath)) {
  console.error('verify-book: lib/generated/registry.json is missing. Run `npm run registry` first.');
  process.exit(1);
}
const registry = JSON.parse(readFileSync(registryPath, 'utf8'));

function findArticles(dir, out = []) {
  for (const d of readdirSync(dir, { withFileTypes: true })) {
    if (d.name === 'node_modules' || d.name.startsWith('.')) continue;
    const full = join(dir, d.name);
    if (d.isDirectory()) findArticles(full, out);
    else if (d.name === 'article.mdx') out.push(full);
  }
  return out.sort();
}

const articles = findArticles(appDir);
const usedFacts = new Set();
let refCount = 0;
for (const file of articles) {
  const src = readFileSync(file, 'utf8');
  const { facts, figures, ledgers, cites } = scanReferences(blankNonProse(src));
  const at = (idx) => `${rel(file)}:${lineAt(src, idx)}`;
  refCount += facts.length + figures.length + ledgers.length + cites.length;

  for (const f of facts) {
    usedFacts.add(f.id);
    const fact = registry.facts[f.id];
    if (!fact) errors.push(`${at(f.index)} <${f.tag} id="${f.id}">: unknown fact`);
    else if (f.ci && !fact.ci_display) errors.push(`${at(f.index)} <Fact id="${f.id}" ci>: the fact has no ci_display`);
  }
  for (const g of figures) {
    const fig = registry.figures[g.id];
    if (!fig) {
      errors.push(`${at(g.index)} <${g.tag} ${g.tag === 'HiddenEffectWeights' ? 'cellsId' : 'id'}="${g.id}">: unknown figure`);
      continue;
    }
    if (g.tag === 'Chart' && !CHART_TYPES.includes(fig.type)) {
      const widget = Object.entries(WIDGET_DATA).find(([, w]) => w.type === fig.type);
      errors.push(`${at(g.index)} <Chart id="${g.id}">: "${fig.type}" is widget data${widget ? `; use <${widget[0]} ${widget[1].prop}="${g.id}" />` : ''}`);
    } else if (WIDGET_DATA[g.tag] && fig.type !== WIDGET_DATA[g.tag].type) {
      errors.push(`${at(g.index)} <${g.tag}>: needs a "${WIDGET_DATA[g.tag].type}" figure, but "${g.id}" is "${fig.type}"`);
    }
  }
  for (const l of ledgers) {
    const ledger = registry.ledgers[l.id];
    if (!ledger) errors.push(`${at(l.index)} <Ledger id="${l.id}">: unknown ledger`);
    else for (const fid of ledger.facts ?? []) usedFacts.add(fid);
  }
  for (const c of cites) {
    if (!c.ids.length) errors.push(`${at(c.index)} <Cite>: empty id`);
    for (const k of c.ids) {
      if (!registry.references[k]) errors.push(`${at(c.index)} <Cite id="${c.raw}">: "${k}" is not in data/references.json`);
    }
  }
}
for (const id of Object.keys(registry.facts)) {
  if (!usedFacts.has(id)) warnings.push(`orphan fact "${id}" is cited by no article.mdx`);
}

// ------------------------------------------------------------------ (c) wiring
const configBase = /const BASE_PATH = ['"]([^'"]*)['"]/.exec(readFileSync(join(root, 'next.config.ts'), 'utf8'));
const siteBase = /export const BASE_PATH = ['"]([^'"]*)['"]/.exec(readFileSync(join(root, 'lib', 'site.ts'), 'utf8'));
if (!configBase || !siteBase || configBase[1] !== siteBase[1]) {
  errors.push(`base path mismatch: next.config.ts has ${configBase?.[1] ?? '?'}, lib/site.ts has ${siteBase?.[1] ?? '?'}`);
}
const mdxComponents = readFileSync(join(root, 'mdx-components.tsx'), 'utf8');
for (const name of GLOBAL_COMPONENTS) {
  if (!new RegExp(`^\\s*${name},?\\s*$`, 'm').test(mdxComponents)) errors.push(`mdx-components.tsx does not register <${name}>`);
}

// ------------------------------------------------------------------ report
for (const w of warnings) console.warn(`verify-book: warn   ${w}`);
for (const e of errors) console.error(`verify-book: ERROR  ${e}`);
console.log(
  `verify-book: ${entries.length} TOC entries (${entries.length - placeholders} exported, ${placeholders} placeholder), ` +
    `${articles.length} article(s), ${refCount} data reference(s); ${errors.length} error(s), ${warnings.length} warning(s)`,
);
process.exit(errors.length ? 1 : 0);
