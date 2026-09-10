#!/usr/bin/env node
/**
 * check-mdx — compile an MDX chapter with the SAME remark/rehype pipeline the
 * site uses, and check that every data reference resolves. Runs from any cwd,
 * so chapter authors working in Box can check a draft without a site build.
 *
 *   node C:/github/weights-book/scripts/check-mdx.mjs <article.mdx> \
 *        [--data <artifacts-dir>]... [--refs <references.json>] [--strict]
 *
 *   --data    an artifacts dir holding manifest.json, facts.json, ledger.json,
 *             figures/*.json. Repeatable (for cross-chapter references). The
 *             FIRST --data is the chapter's own; orphan facts are checked there.
 *   --refs    references registry; default <repo>/data/references.json if present.
 *   --strict  warnings (orphan facts, hand-typed numbers) become errors.
 *
 * Exit 1 on any error. See the book CONTRACT, sections 5 and 8.
 */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { dirname, join, resolve, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from '@mdx-js/mdx';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeSlug from 'rehype-slug';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const macros = JSON.parse(readFileSync(join(root, 'lib', 'katex-macros.json'), 'utf8'));

/** Available in every chapter without an import (mdx-components.tsx). */
export const GLOBAL_COMPONENTS = [
  'Fact', 'KeyNumber', 'Chart', 'Figure', 'Ledger', 'Callout', 'SideNote', 'Cite',
  'Closing', 'Learned', 'Changed', 'NotEstablished', 'Details',
];
/** Imported explicitly from '@/components/widgets/<Name>'. */
export const WIDGETS = [
  'PopulationSampler', 'WeightBuilder', 'HiddenEffectWeights',
  'EstimandSwitcher', 'ReplicateRanking', 'ClusterDesignWorksheet',
];
const FIGURE_TYPES = ['dot', 'bar', 'line', 'slope', 'table', 'histogram', 'cells', 'estimand-set', 'replicates'];

// ---------------------------------------------------------------- args
const argv = process.argv.slice(2);
if (!argv.length || argv[0].startsWith('--')) {
  console.error('usage: check-mdx.mjs <article.mdx> [--data <dir>]... [--refs <file>] [--strict]');
  process.exit(2);
}
const mdxPath = resolve(argv[0]);
const dataDirs = [];
let refsPath = join(root, 'data', 'references.json');
let strict = false;
for (let i = 1; i < argv.length; i++) {
  if (argv[i] === '--data') dataDirs.push(resolve(argv[++i]));
  else if (argv[i] === '--refs') refsPath = resolve(argv[++i]);
  else if (argv[i] === '--strict') strict = true;
}

const errors = [];
const warnings = [];
const src = readFileSync(mdxPath, 'utf8');
const lineOf = (idx) => src.slice(0, idx).split('\n').length;

// ---------------------------------------------------------------- 1. compile
try {
  const file = await compile(
    { path: mdxPath, value: src },
    {
      remarkPlugins: [remarkGfm, [remarkMath, { singleDollarTextMath: false }]],
      rehypePlugins: [rehypeSlug, [rehypeKatex, { macros, strict: 'ignore' }]],
    },
  );
  for (const m of file.messages) {
    const where = m.line ? `line ${m.line}` : '';
    const cause = m.cause && m.cause.message ? ` (${m.cause.message})` : '';
    if (m.source === 'rehype-katex') errors.push(`KaTeX ${where}: ${m.reason}${cause}`);
    else warnings.push(`${m.source ?? 'mdx'} ${where}: ${m.reason}`);
  }
} catch (e) {
  errors.push(`MDX syntax (line ${e.line ?? '?'}, col ${e.column ?? '?'}): ${e.reason ?? e.message}`);
}

// Source with fenced code, inline code, and math blanked out (same length, so
// line numbers survive) for the lints below.
const blank = (m) => m.replace(/[^\n]/g, ' ');
const stripped = src
  .replace(/```[\s\S]*?```/g, blank)
  .replace(/\$\$[\s\S]*?\$\$/g, blank)
  .replace(/`[^`\n]*`/g, blank)
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, blank);

// ---------------------------------------------------------------- 2. components
const imported = new Set();
const importRe = /^import\s+(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s+['"]([^'"]+)['"]/gm;
for (const m of src.matchAll(importRe)) {
  if (m[1]) imported.add(m[1]);
  const names = (m[2] ?? '').split(',').map((s) => s.trim().split(/\s+as\s+/).pop()).filter(Boolean);
  names.forEach((n) => imported.add(n));
  if (m[3].includes('/components/widgets/')) {
    for (const n of names) if (!WIDGETS.includes(n)) warnings.push(`import of unknown widget "${n}" from ${m[3]}`);
  }
}
const allowed = new Set([...GLOBAL_COMPONENTS, ...imported]);
for (const m of stripped.matchAll(/<([A-Z][A-Za-z0-9]*)\b/g)) {
  if (!allowed.has(m[1])) errors.push(`line ${lineOf(m.index)}: unknown component <${m[1]}> (not global, not imported)`);
}

// ---------------------------------------------------------------- 3. data references
const facts = new Map();   // full id -> fact
const figures = new Map(); // full id -> figure json
const ledgers = new Map(); // full id -> ledger
const ownKeys = new Set();
dataDirs.forEach((dir, i) => {
  const mpath = join(dir, 'manifest.json');
  if (!existsSync(mpath)) { errors.push(`--data ${dir}: missing manifest.json`); return; }
  const manifest = JSON.parse(readFileSync(mpath, 'utf8'));
  const key = manifest.key;
  if (!key) { errors.push(`${mpath}: manifest has no "key"`); return; }
  if (i === 0) ownKeys.add(key);
  const fpath = join(dir, 'facts.json');
  if (existsSync(fpath)) {
    const fj = JSON.parse(readFileSync(fpath, 'utf8'));
    for (const [k, f] of Object.entries(fj.facts ?? {})) {
      for (const req of ['value', 'display', 'estimand', 'source']) {
        if (f[req] === undefined || f[req] === '') errors.push(`facts.json ${key}.${k}: missing required field "${req}"`);
      }
      facts.set(`${key}.${k}`, f);
    }
  }
  const lpath = join(dir, 'ledger.json');
  if (existsSync(lpath)) {
    const lj = JSON.parse(readFileSync(lpath, 'utf8'));
    for (const [k, l] of Object.entries(lj.ledgers ?? {})) ledgers.set(`${key}.${k}`, l);
  }
  const gdir = join(dir, 'figures');
  if (existsSync(gdir)) {
    for (const fn of readdirSync(gdir).filter((f) => f.endsWith('.json'))) {
      const g = JSON.parse(readFileSync(join(gdir, fn), 'utf8'));
      const id = `${key}.${basename(fn, '.json')}`;
      if (!FIGURE_TYPES.includes(g.type)) errors.push(`figure ${id}: unknown type "${g.type}"`);
      if (!g.alt) errors.push(`figure ${id}: missing "alt" text`);
      figures.set(id, g);
    }
  }
});

const checked = dataDirs.length > 0;
const loadedKeys = new Set([...facts.keys(), ...figures.keys(), ...ledgers.keys()].map((k) => k.split('.')[0]));
const usedFacts = new Set();
const ref = (kind, id, idx, table) => {
  if (!checked) return;
  if (!id.includes('.')) { errors.push(`line ${lineOf(idx)}: ${kind} id "${id}" must be namespaced, e.g. "ch1.${id}"`); return; }
  if (table.has(id)) return;
  if (loadedKeys.has(id.split('.')[0])) errors.push(`line ${lineOf(idx)}: ${kind} "${id}" not found`);
  else warnings.push(`line ${lineOf(idx)}: ${kind} "${id}" belongs to a chapter not passed with --data (not checked)`);
};
for (const m of stripped.matchAll(/<(Fact|KeyNumber)\b[^>]*?\bid=["']([^"']+)["']/g)) { usedFacts.add(m[2]); ref('fact', m[2], m.index, facts); }
for (const m of stripped.matchAll(/<(Chart|EstimandSwitcher|ReplicateRanking)\b[^>]*?\bid=["']([^"']+)["']/g)) ref('figure', m[2], m.index, figures);
for (const m of stripped.matchAll(/<HiddenEffectWeights\b[^>]*?\bcellsId=["']([^"']+)["']/g)) ref('figure', m[1], m.index, figures);
for (const m of stripped.matchAll(/<Ledger\b[^>]*?\bid=["']([^"']+)["']/g)) ref('ledger', m[1], m.index, ledgers);
if (checked) {
  for (const id of facts.keys()) {
    if (ownKeys.has(id.split('.')[0]) && !usedFacts.has(id)) warnings.push(`orphan fact "${id}" is never cited in this chapter`);
  }
}

// citations
const cites = [...stripped.matchAll(/<Cite\b[^>]*?\bid=["']([^"']+)["']/g)];
if (cites.length) {
  if (existsSync(refsPath)) {
    const refs = JSON.parse(readFileSync(refsPath, 'utf8'));
    const keys = new Set(Object.keys(refs.references ?? refs));
    for (const m of cites) {
      for (const id of m[1].split(',').map((s) => s.trim())) {
        if (!keys.has(id)) warnings.push(`line ${lineOf(m.index)}: citation "${id}" not in ${basename(refsPath)}`);
      }
    }
  } else {
    warnings.push(`${cites.length} <Cite> tags not checked (no references registry at ${refsPath})`);
  }
}

// ---------------------------------------------------------------- 4. hand-typed numbers (heuristic)
const prose = stripped
  .replace(/^(import|export)\b.*$/gm, blank)
  .replace(/<[^>]*>/g, blank)
  .replace(/^#{1,6}\s.*$/gm, blank);
const numberPattern = /(?<![\w.])(\$\s?\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?\s?%|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+)(?![\w])/g;
for (const m of prose.matchAll(numberPattern)) {
  warnings.push(`line ${lineOf(m.index)}: possible hand-typed number "${m[1].trim()}" (use <Fact id="..."/>, or explain in NOTES.md)`);
}

// ---------------------------------------------------------------- report
const name = basename(mdxPath);
for (const e of errors) console.log(`ERROR   ${name}: ${e}`);
for (const w of warnings) console.log(`${strict ? 'ERROR' : 'warn '}   ${name}: ${w}`);
const nErr = errors.length + (strict ? warnings.length : 0);
const loaded = checked ? `; ${facts.size} facts, ${figures.size} figures, ${ledgers.size} ledgers loaded` : '; no --data given, references not checked';
console.log(`check-mdx: ${name}: ${errors.length} error(s), ${warnings.length} warning(s)${loaded}`);
process.exit(nErr ? 1 : 0);
