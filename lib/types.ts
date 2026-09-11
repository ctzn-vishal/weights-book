/**
 * Shared types for the book's data artifacts (docs/CONTRACT.md, section 5).
 * Python build scripts in Box produce these shapes; lib/registry.ts loads them;
 * prose components, charts, and widgets consume them. Keep in step with the
 * contract: a field added here must be added there.
 */

export type Format =
  | 'pct0' | 'pct1' | 'pct2'
  | 'num0' | 'num1' | 'num2' | 'num3'
  | 'int' | 'usd0' | 'min0' | 'min1' | 'ratio2';

/** Colour by meaning, never by hue. Maps to the --role-* / --cat-* tokens. */
export type Role =
  | 'weighted' | 'unweighted' | 'design' | 'naive' | 'truth' | 'benchmark'
  | 'treated' | 'control' | 'highlight' | 'muted'
  | 'cat1' | 'cat2' | 'cat3' | 'cat4' | 'cat5' | 'cat6' | 'cat7' | 'cat8';

export interface Fact {
  value: number | string | null;
  /** Exactly the string the reader sees. Formatted in Python, printed here. */
  display: string;
  unit?: string | null;
  se?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  ci_display?: string | null;
  df?: number | null;
  n?: number | null;
  weight?: string | null;
  variance?: string | null;
  estimand: string;
  source: string;
  benchmark?: string | null;
  note?: string | null;
}

/** The Analysis Ledger (v3 section 2.1). */
export interface Ledger {
  title: string;
  target_population: string;
  estimand: string;
  estimator: string;
  explicit_weights: string;
  implicit_weights: string;
  randomness: string;
  variance_estimator: string;
  assumptions: string;
  facts?: string[];
}

interface FigureBase {
  title?: string;
  subtitle?: string;
  /** Required: one sentence saying what the chart shows. */
  alt: string;
  format?: Format;
  source?: string;
  note?: string;
}

export interface DotRow {
  label: string;
  estimate: number;
  ci_low?: number | null;
  ci_high?: number | null;
  group?: string;
  role?: Role;
  n?: number | null;
}
export interface DotFigure extends FigureBase {
  type: 'dot';
  rows: DotRow[];
  x_label?: string;
  reference?: { value: number; label: string };
  domain?: [number, number];
}

export interface BarRow {
  label: string;
  value: number;
  ci_low?: number | null;
  ci_high?: number | null;
  role?: Role;
}
export interface BarFigure extends FigureBase {
  type: 'bar';
  rows: BarRow[];
  x_label?: string;
  domain?: [number, number];
}

export interface LinePoint {
  x: number;
  y: number;
  lo?: number | null;
  hi?: number | null;
}
/** `segments` are break segments: a line is never drawn across a series break. */
export interface LineSeries {
  name: string;
  role?: Role;
  segments: LinePoint[][];
}
export interface LineFigure extends FigureBase {
  type: 'line';
  series: LineSeries[];
  x_label?: string;
  y_label?: string;
  annotations?: { x: number; label: string }[];
  y_domain?: [number, number];
}

export interface SlopeRow {
  label: string;
  left: number;
  right: number;
  role?: Role;
}
export interface SlopeFigure extends FigureBase {
  type: 'slope';
  rows: SlopeRow[];
  left_label: string;
  right_label: string;
}

export interface TableColumn {
  key: string;
  label: string;
  format?: Format;
  align?: 'left' | 'right' | 'center';
}
export interface TableFigure extends FigureBase {
  type: 'table';
  columns: TableColumn[];
  rows: Record<string, string | number | null>[];
  highlight_key?: string;
}

export interface HistogramFigure extends FigureBase {
  type: 'histogram';
  bins: { x0: number; x1: number; count: number }[];
  x_label?: string;
  y_label?: string;
  markers?: { x: number; label: string }[];
}

// ------------------------------------------------------------ widget data

export interface Cell {
  label: string;
  pop_share: number;
  treat_share: number;
  effect: number;
  effect_se?: number | null;
  n: number;
}
export interface CellsFigure extends FigureBase {
  type: 'cells';
  outcome_label: string;
  treatment_label: string;
  effect_format?: Format;
  cells: Cell[];
  ols_coef?: number | null;
  wls_coef?: number | null;
}

export interface EstimandOption {
  id: string;
  label: string;
  unit: string;
  weight: string;
  estimate: number;
  display: string;
  n: number;
  note?: string | null;
  ledger?: string | null;
}
export interface EstimandSetFigure extends FigureBase {
  type: 'estimand-set';
  question: string;
  options: EstimandOption[];
}

export interface ReplicateUnit {
  id: string;
  label: string;
  estimate: number;
  reps: number[];
  /** Optional naive iid SE, shown by ReplicateRanking's comparison view. */
  naive_se?: number | null;
}
/**
 * SDR replicate estimates. Var(theta) = scale * sum_r (theta_r - theta)^2, so a
 * single replicate deviation has variance Var/(scale * n_reps). Views that treat
 * replicates as draws must rescale deviations by sqrt(scale * n_reps) (= 2 for
 * ACS SDR, where scale = 4/80).
 */
export interface ReplicatesFigure extends FigureBase {
  type: 'replicates';
  measure_label: string;
  method: string;
  n_reps: number;
  scale: number;
  top_k: number;
  units: ReplicateUnit[];
}

export type CodeLang = 'r' | 'python' | 'stata';
export interface VcovOption {
  key: string;
  label: string;
  /** One or two sentences: what this estimator lets the errors do. */
  assumes: string;
  verdict: 'right' | 'valid' | 'wrong' | 'noisy';
  role?: Role;
  se: number;
  ratio: number;
  ci_low: number;
  ci_high: number;
  p: number;
  se_display: string;
  ratio_display: string;
  p_display: string;
  ci_display: string;
  code: Record<CodeLang, string>;
  /** The substring of `code` that changes between options (highlighted). */
  arg: Record<CodeLang, string>;
}
/** Lab 6: one coefficient under several vcov arguments (VcovExplorer). */
export interface VcovMenuFigure extends FigureBase {
  type: 'vcov-menu';
  coef: number;
  coef_display: string;
  truth: number;
  n_obs: number;
  states: number;
  years: number;
  treated_states: number;
  options: VcovOption[];
}

export type ChartFigure = DotFigure | BarFigure | LineFigure | SlopeFigure | TableFigure | HistogramFigure;
export type WidgetFigure = CellsFigure | EstimandSetFigure | ReplicatesFigure | VcovMenuFigure;
export type Figure = ChartFigure | WidgetFigure;

// ------------------------------------------------------------ references

export interface Reference {
  /** Author string as cited: "Solon, Haider, and Wooldridge". */
  short: string;
  year: number | string;
  title: string;
  authors?: string[];
  venue?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  publisher?: string | null;
  doi?: string | null;
  url?: string | null;
  /** How and when the entry was checked, e.g. "doi.org, 2026-09-10". */
  verified?: string | null;
}

export interface Manifest {
  key: string;
  slug: string;
  status?: 'draft' | 'review' | 'final';
  inputs?: { path: string; rows?: number; note?: string }[];
  code?: string;
  validation?: unknown[];
  generated_at?: string;
}

export interface Registry {
  facts: Record<string, Fact>;
  figures: Record<string, Figure>;
  ledgers: Record<string, Ledger>;
  references: Record<string, Reference>;
}
