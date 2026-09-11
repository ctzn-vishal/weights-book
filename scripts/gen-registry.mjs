#!/usr/bin/env node
/**
 * gen-registry — collect every exported artifact into lib/generated/registry.json,
 * the file lib/registry.ts serves to components (getFact, getFigure, ...).
 *
 *   node scripts/gen-registry.mjs        (run by `npm run registry`, dev, build, typecheck)
 *
 * Sources, all relative to the repo root:
 *   app/**\/data/manifest.json          one per chapter (and app/dev/**); gives the key
 *   app/**\/data/facts.json             {key, facts:{<fact_key>: Fact}}
 *   app/**\/data/ledger.json            {key, ledgers:{<ledger_key>: Ledger}}
 *   app/**\/data/figures/*.json         one figure per file; id = <key>.<file stem>
 *   data/references.json               {references:{<cite_key>: Reference}}
 *
 * Global ids are "<manifest.key>.<local key>" (docs/CONTRACT.md §4–5). Output is
 * deterministic: object keys sorted at every depth, arrays kept in order, and
 * the file rewritten only when its content changes (atomically, so a parallel
 * build never reads half a file).
 *
 * Fails (exit 1) on: a duplicate manifest key or global id, a figure without a
 * known `type` or without `alt`, a figure whose required arrays are missing,
 * a fact without its required fields, unreadable JSON. Everything else that
 * looks wrong is a warning.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  FACT_REQUIRED, FIGURE_TYPES, FORMATS, LEDGER_FIELDS, ROLES, VARIANCE_RE,
} from './lib/book-contract.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const appDir = join(root, 'app');
const refsPath = join(root, 'data', 'references.json');
const outPath = join(root, 'lib', 'generated', 'registry.json');
const pagesPath = join(root, 'lib', 'generated', 'pages.json');

const errors = [];
const warnings = [];
const rel = (p) => relative(root, p).split('\\').join('/');

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch (e) {
    errors.push(`${rel(path)}: cannot read JSON (${e.message})`);
    return null;
  }
}

const SKIP = new Set(['node_modules', '.git']);
/** Every app/**\/data directory that holds a manifest.json, sorted for determinism. */
function findDataDirs(dir, out = []) {
  for (const d of readdirSync(dir, { withFileTypes: true })) {
    if (!d.isDirectory() || SKIP.has(d.name) || d.name.startsWith('.next')) continue;
    const full = join(dir, d.name);
    if (d.name === 'data' && existsSync(join(full, 'manifest.json'))) out.push(full);
    findDataDirs(full, out);
  }
  return out.sort();
}

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isNumOrNull = (v) => v === null || v === undefined || isNum(v);

/** Structural checks per figure type: problems that would crash or silently mis-draw a chart. */
function checkFigure(id, g) {
  const fail = (msg) => errors.push(`figure ${id}: ${msg}`);
  const warn = (msg) => warnings.push(`figure ${id}: ${msg}`);
  if (!isObj(g)) return fail('not a JSON object');
  if (!FIGURE_TYPES.includes(g.type)) fail(`missing or unknown "type" ${JSON.stringify(g.type)} (expected one of ${FIGURE_TYPES.join(', ')})`);
  if (typeof g.alt !== 'string' || !g.alt.trim()) fail('missing "alt" (one sentence saying what the chart shows)');
  if (g.format !== undefined && g.format !== null && !FORMATS.includes(g.format)) fail(`unknown "format" ${JSON.stringify(g.format)}`);
  const role = (r, where) => {
    if (r !== undefined && r !== null && !ROLES.includes(r)) fail(`${where}: unknown role ${JSON.stringify(r)}`);
  };
  const rows = (key) => {
    if (!Array.isArray(g[key])) { fail(`"${key}" must be an array`); return []; }
    if (!g[key].length) warn(`"${key}" is empty`);
    return g[key];
  };
  switch (g.type) {
    case 'dot':
      rows('rows').forEach((r, i) => {
        if (typeof r?.label !== 'string') fail(`rows[${i}].label must be a string`);
        if (!isNumOrNull(r?.estimate)) fail(`rows[${i}].estimate must be a number (or null when suppressed)`);
        if (!isNumOrNull(r?.ci_low) || !isNumOrNull(r?.ci_high)) fail(`rows[${i}]: ci_low/ci_high must be numbers or null`);
        role(r?.role, `rows[${i}]`);
      });
      if (g.reference !== undefined && (!isObj(g.reference) || !isNum(g.reference.value))) fail('"reference" must be {value, label}');
      break;
    case 'bar':
      rows('rows').forEach((r, i) => {
        if (typeof r?.label !== 'string') fail(`rows[${i}].label must be a string`);
        if (!isNumOrNull(r?.value)) fail(`rows[${i}].value must be a number (or null when suppressed)`);
        if (!isNumOrNull(r?.ci_low) || !isNumOrNull(r?.ci_high)) fail(`rows[${i}]: ci_low/ci_high must be numbers or null`);
        role(r?.role, `rows[${i}]`);
      });
      break;
    case 'line':
      rows('series').forEach((s, i) => {
        if (typeof s?.name !== 'string') fail(`series[${i}].name must be a string`);
        role(s?.role, `series[${i}]`);
        if (!Array.isArray(s?.segments) || !s.segments.every(Array.isArray)) {
          fail(`series[${i}].segments must be an array of arrays of {x, y}`);
          return;
        }
        s.segments.forEach((seg, j) => seg.forEach((p, k) => {
          if (!isNum(p?.x) || !isNumOrNull(p?.y)) fail(`series[${i}].segments[${j}][${k}] needs numeric x and y`);
        }));
      });
      (g.annotations ?? []).forEach((a, i) => { if (!isNum(a?.x)) fail(`annotations[${i}].x must be a number`); });
      break;
    case 'slope':
      rows('rows').forEach((r, i) => {
        if (typeof r?.label !== 'string') fail(`rows[${i}].label must be a string`);
        if (!isNum(r?.left) || !isNum(r?.right)) fail(`rows[${i}]: left and right must be numbers`);
        role(r?.role, `rows[${i}]`);
      });
      if (typeof g.left_label !== 'string' || typeof g.right_label !== 'string') fail('"left_label" and "right_label" are required');
      break;
    case 'table':
      rows('columns').forEach((c, i) => {
        if (typeof c?.key !== 'string' || typeof c?.label !== 'string') fail(`columns[${i}] needs {key, label}`);
        if (c?.format !== undefined && c?.format !== null && !FORMATS.includes(c.format)) fail(`columns[${i}]: unknown format ${JSON.stringify(c.format)}`);
      });
      rows('rows').forEach((r, i) => { if (!isObj(r)) fail(`rows[${i}] must be an object`); });
      break;
    case 'histogram':
      rows('bins').forEach((b, i) => {
        if (!isNum(b?.x0) || !isNum(b?.x1) || !isNum(b?.count)) fail(`bins[${i}] needs numeric x0, x1, count`);
      });
      (g.markers ?? []).forEach((m, i) => { if (!isNum(m?.x)) fail(`markers[${i}].x must be a number`); });
      break;
    case 'cells':
      rows('cells');
      break;
    case 'estimand-set':
      rows('options');
      break;
    case 'replicates':
      rows('units');
      break;
    default:
      break;
  }
}

function checkFact(id, f) {
  if (!isObj(f)) { errors.push(`fact ${id}: not a JSON object`); return; }
  for (const k of FACT_REQUIRED) {
    const v = f[k];
    const missing = k === 'value' ? v === undefined : v === undefined || v === null || v === '';
    if (missing) errors.push(`fact ${id}: missing required field "${k}"`);
  }
  if (f.display !== undefined && typeof f.display !== 'string') errors.push(`fact ${id}: "display" must be a string`);
  if (f.variance && !VARIANCE_RE.test(f.variance)) warnings.push(`fact ${id}: unrecognized variance "${f.variance}"`);
  if (f.ci_display && (f.ci_low === null || f.ci_low === undefined)) warnings.push(`fact ${id}: has ci_display but no ci_low`);
}

function checkLedger(id, l) {
  if (!isObj(l)) { errors.push(`ledger ${id}: not a JSON object`); return; }
  if (!l.title) errors.push(`ledger ${id}: missing "title"`);
  const missing = LEDGER_FIELDS.filter((k) => !l[k]);
  if (missing.length) warnings.push(`ledger ${id}: empty field(s) ${missing.join(', ')}`);
  if (l.facts !== undefined && !Array.isArray(l.facts)) errors.push(`ledger ${id}: "facts" must be an array of fact ids`);
}

// ------------------------------------------------------------------ collect
const facts = {};
const figures = {};
const ledgers = {};
const manifests = {};
const keyOwner = new Map();

function put(table, kind, id, value, src) {
  if (Object.hasOwn(table, id)) {
    errors.push(`duplicate ${kind} id "${id}" (${src})`);
    return;
  }
  table[id] = value;
}

for (const dir of findDataDirs(appDir)) {
  const manifest = readJson(join(dir, 'manifest.json'));
  if (!manifest) continue;
  const key = manifest.key;
  if (typeof key !== 'string' || !/^[A-Za-z][A-Za-z0-9_]*$/.test(key)) {
    errors.push(`${rel(dir)}/manifest.json: "key" must be an identifier like "ch1" (got ${JSON.stringify(key)})`);
    continue;
  }
  if (keyOwner.has(key)) {
    errors.push(`duplicate manifest key "${key}": ${keyOwner.get(key)} and ${rel(dir)}`);
    continue;
  }
  keyOwner.set(key, rel(dir));
  // generated_at is the one field allowed to change between identical runs; keep it out.
  const stable = { ...manifest, dir: rel(dir) };
  delete stable.generated_at;
  manifests[key] = stable;

  const fpath = join(dir, 'facts.json');
  if (existsSync(fpath)) {
    const fj = readJson(fpath);
    if (fj) {
      if (fj.key !== undefined && fj.key !== key) errors.push(`${rel(fpath)}: key "${fj.key}" does not match manifest key "${key}"`);
      if (!isObj(fj.facts)) errors.push(`${rel(fpath)}: expected {key, facts:{...}}`);
      for (const [k, f] of Object.entries(fj.facts ?? {})) {
        checkFact(`${key}.${k}`, f);
        put(facts, 'fact', `${key}.${k}`, f, rel(fpath));
      }
    }
  }

  const lpath = join(dir, 'ledger.json');
  if (existsSync(lpath)) {
    const lj = readJson(lpath);
    if (lj) {
      if (lj.key !== undefined && lj.key !== key) errors.push(`${rel(lpath)}: key "${lj.key}" does not match manifest key "${key}"`);
      if (!isObj(lj.ledgers)) errors.push(`${rel(lpath)}: expected {key, ledgers:{...}}`);
      for (const [k, l] of Object.entries(lj.ledgers ?? {})) {
        checkLedger(`${key}.${k}`, l);
        put(ledgers, 'ledger', `${key}.${k}`, l, rel(lpath));
      }
    }
  }

  const gdir = join(dir, 'figures');
  if (existsSync(gdir)) {
    for (const fn of readdirSync(gdir).filter((f) => f.endsWith('.json')).sort()) {
      const g = readJson(join(gdir, fn));
      if (!g) continue;
      const id = `${key}.${basename(fn, '.json')}`;
      checkFigure(id, g);
      put(figures, 'figure', id, g, `${rel(gdir)}/${fn}`);
    }
  }
}

// Ledger fact lists must point at real facts (the Ledger component renders them).
for (const [id, l] of Object.entries(ledgers)) {
  for (const fid of Array.isArray(l.facts) ? l.facts : []) {
    if (!Object.hasOwn(facts, fid)) errors.push(`ledger ${id}: lists unknown fact "${fid}"`);
  }
}

let references = {};
if (existsSync(refsPath)) {
  const rj = readJson(refsPath);
  if (rj) {
    references = isObj(rj.references) ? rj.references : {};
    if (!isObj(rj.references)) errors.push('data/references.json: expected {references:{<key>: Reference}}');
    for (const [k, r] of Object.entries(references)) {
      if (!isObj(r) || !r.short || r.year === undefined || !r.title) errors.push(`reference ${k}: needs short, year, and title`);
    }
  }
} else {
  warnings.push('data/references.json not found: <Cite> has no references to resolve');
}

// ------------------------------------------------------------------ write
function sortDeep(v) {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (isObj(v)) {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = sortDeep(v[k]);
    return out;
  }
  return v;
}

for (const w of warnings) console.warn(`gen-registry: warn   ${w}`);
if (errors.length) {
  for (const e of errors) console.error(`gen-registry: ERROR  ${e}`);
  console.error(`gen-registry: ${errors.length} error(s); ${rel(outPath)} not written.`);
  process.exit(1);
}

/** Write only when the content changed (keeps `next dev` from reloading), atomically. */
function writeIfChanged(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  if (existsSync(path) && readFileSync(path, 'utf8') === content) return false;
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, content);
  renameSync(tmp, path);
  return true;
}

const json = `${JSON.stringify(sortDeep({ facts, figures, ledgers, manifests, references }))}\n`;
const changed = writeIfChanged(outPath, json);

// Which chapter directories already have a page: the placeholder route
// (app/[slug]) serves the rest, and the contents marks them "soon".
const PAGE_FILES = ['page.tsx', 'page.ts', 'page.jsx', 'page.js', 'page.mdx', 'page.md'];
const pages = readdirSync(appDir, { withFileTypes: true })
  .filter((d) => d.isDirectory() && /^(ch\d|appendix-)/.test(d.name))
  .filter((d) => PAGE_FILES.some((f) => existsSync(join(appDir, d.name, f))))
  .map((d) => d.name)
  .sort();
writeIfChanged(pagesPath, `${JSON.stringify({ pages })}\n`);

const n = (o) => Object.keys(o).length;
console.log(
  `gen-registry: ${n(manifests)} manifest(s), ${n(facts)} facts, ${n(figures)} figures, ${n(ledgers)} ledgers, ` +
  `${n(references)} references -> ${rel(outPath)}${changed ? '' : ' (unchanged)'}; ${pages.length} chapter page(s)`,
);
