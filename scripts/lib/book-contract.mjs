/**
 * The parts of docs/CONTRACT.md that scripts check mechanically, in one place:
 * component and widget names, figure types, format codes, roles, and the
 * source scanner that finds data references in MDX. Imported by
 * check-mdx.mjs, gen-registry.mjs, and verify-book.mjs so the three never
 * disagree about what a valid reference is.
 *
 * Plain ESM with no dependencies: check-mdx runs from any cwd.
 */

/** Available in every chapter without an import (mdx-components.tsx). */
export const GLOBAL_COMPONENTS = [
  'Fact', 'KeyNumber', 'Chart', 'Figure', 'Ledger', 'Callout', 'SideNote', 'Cite',
  'Closing', 'Learned', 'Changed', 'NotEstablished', 'Details',
];

/** Imported explicitly from '@/components/widgets/<Name>'. */
export const WIDGETS = [
  'PopulationSampler', 'WeightBuilder', 'HiddenEffectWeights',
  'EstimandSwitcher', 'ReplicateRanking', 'ClusterDesignWorksheet',
  'VcovExplorer', 'RejectionGrid',
];

/** Widgets that read a figure artifact: the prop naming it and the type it must have. */
export const WIDGET_DATA = {
  EstimandSwitcher: { prop: 'id', type: 'estimand-set' },
  ReplicateRanking: { prop: 'id', type: 'replicates' },
  HiddenEffectWeights: { prop: 'cellsId', type: 'cells' },
  VcovExplorer: { prop: 'id', type: 'vcov-menu' },
  RejectionGrid: { prop: 'id', type: 'table' },
};

export const CHART_TYPES = ['dot', 'bar', 'line', 'slope', 'table', 'histogram'];
export const WIDGET_TYPES = ['cells', 'estimand-set', 'replicates', 'vcov-menu'];
export const FIGURE_TYPES = [...CHART_TYPES, ...WIDGET_TYPES];

export const FORMATS = ['pct0', 'pct1', 'pct2', 'num0', 'num1', 'num2', 'num3', 'int', 'usd0', 'min0', 'min1', 'ratio2'];

export const ROLES = [
  'weighted', 'unweighted', 'design', 'naive', 'truth', 'benchmark', 'treated', 'control',
  'highlight', 'muted', 'cat1', 'cat2', 'cat3', 'cat4', 'cat5', 'cat6', 'cat7', 'cat8',
];

export const FACT_REQUIRED = ['value', 'display', 'estimand', 'source'];

export const LEDGER_FIELDS = [
  'target_population', 'estimand', 'estimator', 'explicit_weights',
  'implicit_weights', 'randomness', 'variance_estimator', 'assumptions',
];

export const VARIANCE_RE =
  /^(taylor|replicate_sdr\(\d+\)|replicate_brr|weights_only_understated|cluster_robust\([^)]+\)|wild_cluster_bootstrap\([^)]+\)|none|simulation)$/;

/**
 * Blank out fenced code, math, inline code, and MDX comments, keeping the
 * string the same length so match indices still map to source lines.
 */
export function blankNonProse(src) {
  const blank = (m) => m.replace(/[^\n]/g, ' ');
  return src
    .replace(/```[\s\S]*?```/g, blank)
    .replace(/\$\$[\s\S]*?\$\$/g, blank)
    .replace(/`[^`\n]*`/g, blank)
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, blank);
}

/** 1-based line number of a character index. */
export function lineAt(src, idx) {
  return src.slice(0, idx).split('\n').length;
}

/**
 * Every data reference in (blanked) MDX source.
 * Returns arrays of { id, index, tag } plus, for facts, whether `ci` is set.
 */
export function scanReferences(stripped) {
  const facts = [];
  for (const m of stripped.matchAll(/<(Fact|KeyNumber)\b[^>]*?\bid=["']([^"']+)["']/g)) {
    facts.push({ tag: m[1], id: m[2], index: m.index });
  }
  // `ci` is a bare boolean attribute on <Fact>; read it from the whole tag.
  for (const m of stripped.matchAll(/<Fact\b([^>]*?)\/?>/g)) {
    const idm = /\bid=["']([^"']+)["']/.exec(m[1]);
    if (!idm) continue;
    const attrs = m[1].replace(/=["'][^"']*["']/g, '');
    const hit = facts.find((f) => f.index === m.index);
    if (hit) hit.ci = /(^|\s)ci(\s|=|$)/.test(attrs);
  }
  const figures = [];
  for (const m of stripped.matchAll(/<(Chart|EstimandSwitcher|ReplicateRanking)\b[^>]*?\bid=["']([^"']+)["']/g)) {
    figures.push({ tag: m[1], id: m[2], index: m.index });
  }
  for (const m of stripped.matchAll(/<HiddenEffectWeights\b[^>]*?\bcellsId=["']([^"']+)["']/g)) {
    figures.push({ tag: 'HiddenEffectWeights', id: m[1], index: m.index });
  }
  const ledgers = [];
  for (const m of stripped.matchAll(/<Ledger\b[^>]*?\bid=["']([^"']+)["']/g)) {
    ledgers.push({ tag: 'Ledger', id: m[1], index: m.index });
  }
  const cites = [];
  for (const m of stripped.matchAll(/<Cite\b[^>]*?\bid=["']([^"']+)["']/g)) {
    cites.push({ tag: 'Cite', ids: m[1].split(',').map((s) => s.trim()).filter(Boolean), raw: m[1], index: m.index });
  }
  return { facts, figures, ledgers, cites };
}
