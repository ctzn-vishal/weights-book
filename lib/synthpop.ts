/**
 * The canonical synthetic population (v3 section 9.1).
 *
 * Every interactive in the book draws from this one population, so the book is
 * cumulative: the adults a reader samples in Chapter 0 are the adults whose
 * weights they build in Chapter 2. Seeded and versioned: the same version and
 * seed give the same 20,000 adults, the same truths, and the same samples on
 * every machine. Change SYNTHPOP_VERSION whenever a change here would move a
 * number a chapter prints.
 *
 * Structure: 200 neighbourhoods x 100 residents. Neighbourhood effect
 * u_j ~ Normal(0, 0.45^2); 30% of neighbourhoods rural. Group G is concentrated
 * in some neighbourhoods and correlated with u_j. Outcomes: `uninsured`
 * (logit model, calibrated to 12% prevalence) and `logwage` with a treatment
 * `wfh` whose effect differs by cell (age group x college degree).
 *
 * "Truths" are computed from the population itself, never from the model
 * parameters, so they are exactly what an estimator is scored against.
 */

export const SYNTHPOP_VERSION = '1.0.0';
export const SYNTHPOP_SEED = 20260910;
export const N_NBHD = 200;
export const PER_NBHD = 100;
export const N_POP = N_NBHD * PER_NBHD;

export const AGE_LABELS = ['18–34', '35–54', '55+'] as const;
export const EDU_LABELS = ['No degree', 'College'] as const;
/** Cells are age group x college degree; index = 3 * college + age. */
export const N_CELLS = 6;
export const CELL_LABELS: readonly string[] = [0, 1].flatMap((c) =>
  AGE_LABELS.map((a) => `${a}, ${c ? 'college' : 'no degree'}`),
);
export const cellIndex = (age: number, college: number): number => 3 * college + age;

/** Model parameters. Documentation for chapter authors; the truths come from the draws. */
export const SYNTHPOP_PARAMS = {
  neighbourhoodSd: 0.45,
  ruralShare: 0.3,
  /** Age-group shares by rural/urban; overall about .34 / .35 / .31. */
  ageShares: { rural: [0.3, 0.34, 0.36], urban: [0.3571, 0.3543, 0.2886] },
  /** logit(neighbourhood G share) = a + 1.1 z_j + 1.0 e_j, z_j = u_j / 0.45; a set so G is 15%. */
  g: { target: 0.15, zLoading: 1.1, noiseSd: 1.0 },
  /** logit P(college) = a + age + rural + G; a set so 35% hold a degree. */
  college: { target: 0.35, age: [0.25, 0.15, -0.4], rural: -0.65, g: -0.45 },
  /** logit P(uninsured) = a + age + college + G + u_j; a set so prevalence is 12%. */
  uninsured: { target: 0.12, age: [0.5, 0, -0.8], college: -0.9, g: 0.85 },
  /** logwage(0) = 3.1 + age + college + G - 0.35 u_j + Normal(0, 0.45^2). */
  wage: { intercept: 3.1, age: [0, 0.22, 0.28], college: 0.42, g: -0.08, u: -0.35, noiseSd: 0.45 },
  /** P(wfh) by [college][age]: about 30% with a degree, 6% without. Depends on the cell only. */
  wfhP: [
    [0.07, 0.06, 0.05],
    [0.33, 0.31, 0.25],
  ],
  /** Effect of wfh on logwage by [college][age]: about 0.20 with a degree, 0.04 without. */
  tau: [
    [0.05, 0.04, 0.03],
    [0.23, 0.2, 0.16],
  ],
  /** logit P(respond) = a + age + college; a set so 55% of the population would respond. */
  response: { target: 0.55, age: [-0.7, 0, 0.55], college: 0.9 },
} as const;

// ------------------------------------------------------------------ randomness

/** mulberry32: a small, fast 32-bit PRNG. Returns uniforms in [0, 1). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a hash of the parts: independent, reproducible streams from one seed. */
export function deriveSeed(...parts: (string | number)[]): number {
  const s = parts.join('|');
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** Box–Muller standard normals from a uniform stream. */
export function makeNormal(rng: () => number): () => number {
  let spare: number | null = null;
  return () => {
    if (spare !== null) {
      const s = spare;
      spare = null;
      return s;
    }
    let u = 0;
    while (u === 0) u = rng();
    const v = rng();
    const r = Math.sqrt(-2 * Math.log(u));
    spare = r * Math.sin(2 * Math.PI * v);
    return r * Math.cos(2 * Math.PI * v);
  };
}

export const expit = (x: number): number => 1 / (1 + Math.exp(-x));
export const logit = (p: number): number => Math.log(p / (1 - p));

/** Intercept a with mean_i expit(a + lin_i) = target (Newton's method; deterministic). */
function calibrateIntercept(lin: ArrayLike<number>, target: number): number {
  let a = logit(target);
  for (let it = 0; it < 50; it++) {
    let f = 0;
    let df = 0;
    for (let i = 0; i < lin.length; i++) {
      const p = expit(a + lin[i]);
      f += p;
      df += p * (1 - p);
    }
    const step = (f / lin.length - target) / (df / lin.length);
    a -= step;
    if (Math.abs(step) < 1e-13) break;
  }
  return a;
}

// ------------------------------------------------------------------ population

/** A raking margin: a category for every population unit, and population totals. */
export interface Margin {
  name: string;
  labels: readonly string[];
  of: (popIndex: number) => number;
  targets: number[];
}

export interface Truths {
  /** Population prevalence of `uninsured`. */
  prevalence: number;
  prevalenceG: number;
  prevalenceNonG: number;
  gShare: number;
  collegeShare: number;
  ruralShare: number;
  ageShares: number[];
  cellShares: number[];
  wfhShare: number;
  wfhShareCollege: number;
  wfhShareNoDegree: number;
  meanLogwage: number;
  /** Mean of tau_i over everyone. */
  pate: number;
  /** Mean of tau_i among residents with wfh = 1. */
  att: number;
  /** Mean of tau_i among residents with wfh = 0. */
  atu: number;
  /** Cell effects tau_g and realized cell treatment shares. */
  cellTau: number[];
  cellP: number[];
  /** Population mean of the true response propensity. */
  responseRate: number;
}

export interface Population {
  version: string;
  seed: number;
  N: number;
  nbhd: Uint16Array;
  rural: Uint8Array;
  age: Uint8Array;
  college: Uint8Array;
  g: Uint8Array;
  cell: Uint8Array;
  pUninsured: Float64Array;
  uninsured: Uint8Array;
  /** logwage with wfh = 0 (the untreated potential outcome). */
  base: Float64Array;
  /** The uniform behind each wfh draw (common random numbers for scenarios). */
  uWfh: Float64Array;
  wfh: Uint8Array;
  tau: Float64Array;
  logwage: Float64Array;
  /** True response propensity (depends on age and college only). */
  rho: Float64Array;
  nbhdU: Float64Array;
  nbhdRural: Uint8Array;
  nbhdGShare: Float64Array;
  truths: Truths;
  /** Known population totals: the raking targets. */
  margins: { ageCollege: Margin; g: Margin };
}

function buildPopulation(seed: number): Population {
  const P = SYNTHPOP_PARAMS;
  const N = N_POP;

  // Neighbourhoods: u_j, exactly 30% rural, and a G share tied to u_j.
  const rngN = mulberry32(deriveSeed(seed, 'neighbourhoods'));
  const normN = makeNormal(rngN);
  const nbhdU = new Float64Array(N_NBHD);
  const zG = new Float64Array(N_NBHD);
  for (let j = 0; j < N_NBHD; j++) {
    const z = normN();
    nbhdU[j] = P.neighbourhoodSd * z;
    zG[j] = P.g.zLoading * z + P.g.noiseSd * normN();
  }
  const order = Array.from({ length: N_NBHD }, (_, j) => j);
  for (let i = N_NBHD - 1; i > 0; i--) {
    const k = Math.floor(rngN() * (i + 1));
    [order[i], order[k]] = [order[k], order[i]];
  }
  const nbhdRural = new Uint8Array(N_NBHD);
  for (let r = 0; r < Math.round(P.ruralShare * N_NBHD); r++) nbhdRural[order[r]] = 1;
  const aG = calibrateIntercept(zG, P.g.target);
  const nbhdGShare = new Float64Array(N_NBHD);
  for (let j = 0; j < N_NBHD; j++) nbhdGShare[j] = expit(aG + zG[j]);

  // Residents: G, then age (by rural/urban).
  const nbhd = new Uint16Array(N);
  const rural = new Uint8Array(N);
  const g = new Uint8Array(N);
  const age = new Uint8Array(N);
  const rngG = mulberry32(deriveSeed(seed, 'group'));
  const rngA = mulberry32(deriveSeed(seed, 'age'));
  for (let i = 0; i < N; i++) {
    const j = Math.floor(i / PER_NBHD);
    nbhd[i] = j;
    rural[i] = nbhdRural[j];
    g[i] = rngG() < nbhdGShare[j] ? 1 : 0;
    const shares = rural[i] ? P.ageShares.rural : P.ageShares.urban;
    const u = rngA();
    age[i] = u < shares[0] ? 0 : u < shares[0] + shares[1] ? 1 : 2;
  }

  // College degree.
  const linC = new Float64Array(N);
  for (let i = 0; i < N; i++) linC[i] = P.college.age[age[i]] + P.college.rural * rural[i] + P.college.g * g[i];
  const aC = calibrateIntercept(linC, P.college.target);
  const rngC = mulberry32(deriveSeed(seed, 'college'));
  const college = new Uint8Array(N);
  const cell = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    college[i] = rngC() < expit(aC + linC[i]) ? 1 : 0;
    cell[i] = cellIndex(age[i], college[i]);
  }

  // Uninsured.
  const linU = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    linU[i] =
      P.uninsured.age[age[i]] + P.uninsured.college * college[i] + P.uninsured.g * g[i] + nbhdU[nbhd[i]];
  }
  const aU = calibrateIntercept(linU, P.uninsured.target);
  const rngU = mulberry32(deriveSeed(seed, 'uninsured'));
  const pUninsured = new Float64Array(N);
  const uninsured = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    pUninsured[i] = expit(aU + linU[i]);
    uninsured[i] = rngU() < pUninsured[i] ? 1 : 0;
  }

  // Wages and working from home.
  const rngW = mulberry32(deriveSeed(seed, 'wage'));
  const normW = makeNormal(rngW);
  const rngD = mulberry32(deriveSeed(seed, 'wfh'));
  const base = new Float64Array(N);
  const uWfh = new Float64Array(N);
  const wfh = new Uint8Array(N);
  const tau = new Float64Array(N);
  const logwage = new Float64Array(N);
  const W = P.wage;
  for (let i = 0; i < N; i++) {
    base[i] =
      W.intercept + W.age[age[i]] + W.college * college[i] + W.g * g[i] + W.u * nbhdU[nbhd[i]] + W.noiseSd * normW();
    uWfh[i] = rngD();
    wfh[i] = uWfh[i] < P.wfhP[college[i]][age[i]] ? 1 : 0;
    tau[i] = P.tau[college[i]][age[i]];
    logwage[i] = base[i] + tau[i] * wfh[i];
  }

  // True response propensity.
  const linR = new Float64Array(N);
  for (let i = 0; i < N; i++) linR[i] = P.response.age[age[i]] + P.response.college * college[i];
  const aR = calibrateIntercept(linR, P.response.target);
  const rho = new Float64Array(N);
  for (let i = 0; i < N; i++) rho[i] = expit(aR + linR[i]);

  // Truths, from the population itself.
  let nG = 0, uG = 0, uNG = 0, nCol = 0, nRur = 0, nWfh = 0, nWfhCol = 0, nWfhNo = 0;
  let sumLw = 0, sumTau = 0, sumTauT = 0, sumTauU = 0, sumRho = 0;
  const ageN = [0, 0, 0];
  const cellN = new Array<number>(N_CELLS).fill(0);
  const cellT = new Array<number>(N_CELLS).fill(0);
  for (let i = 0; i < N; i++) {
    if (g[i]) { nG++; uG += uninsured[i]; } else uNG += uninsured[i];
    nCol += college[i];
    nRur += rural[i];
    ageN[age[i]]++;
    cellN[cell[i]]++;
    cellT[cell[i]] += wfh[i];
    nWfh += wfh[i];
    if (college[i]) nWfhCol += wfh[i]; else nWfhNo += wfh[i];
    sumLw += logwage[i];
    sumTau += tau[i];
    if (wfh[i]) sumTauT += tau[i]; else sumTauU += tau[i];
    sumRho += rho[i];
  }
  const cellTau = Array.from({ length: N_CELLS }, (_, c) => P.tau[c >= 3 ? 1 : 0][c % 3]);
  const truths: Truths = {
    prevalence: (uG + uNG) / N,
    prevalenceG: uG / nG,
    prevalenceNonG: uNG / (N - nG),
    gShare: nG / N,
    collegeShare: nCol / N,
    ruralShare: nRur / N,
    ageShares: ageN.map((a) => a / N),
    cellShares: cellN.map((c) => c / N),
    wfhShare: nWfh / N,
    wfhShareCollege: nWfhCol / nCol,
    wfhShareNoDegree: nWfhNo / (N - nCol),
    meanLogwage: sumLw / N,
    pate: sumTau / N,
    att: sumTauT / nWfh,
    atu: sumTauU / (N - nWfh),
    cellTau,
    cellP: cellT.map((t, c) => t / cellN[c]),
    responseRate: sumRho / N,
  };

  const margins = {
    ageCollege: { name: 'Age × college', labels: CELL_LABELS, of: (i: number) => cell[i], targets: cellN.slice() },
    g: { name: 'Group G', labels: ['Not G', 'G'], of: (i: number) => g[i], targets: [N - nG, nG] },
  };

  return {
    version: SYNTHPOP_VERSION, seed, N, nbhd, rural, age, college, g, cell, pUninsured, uninsured,
    base, uWfh, wfh, tau, logwage, rho, nbhdU, nbhdRural, nbhdGShare, truths, margins,
  };
}

let cached: Population | null = null;
/** The canonical population (built once, about 10 ms). */
export function getPopulation(): Population {
  if (!cached) cached = buildPopulation(SYNTHPOP_SEED);
  return cached;
}

// ------------------------------------------------------------------ sampling

export interface Sample {
  design: 'srs' | 'oversample' | 'cluster';
  seed: number;
  n: number;
  /** Population indices, ascending. */
  idx: Int32Array;
  /** Exact inclusion probabilities pi_i. */
  pi: Float64Array;
  /** Design weights d_i = 1 / pi_i. */
  d: Float64Array;
  /** Neighbourhood of each sampled unit (the cluster id for cluster-robust SEs). */
  cluster: Uint16Array;
  /** Sampling stratum (G for the oversample; 0 otherwise). */
  stratum: Uint8Array;
}

export interface RespondedSample extends Sample {
  responded: Uint8Array;
  /** True response propensity of each sampled unit. */
  rho: Float64Array;
}

const scratchPop = new Int32Array(N_POP);
const scratchNbhd = new Int32Array(N_NBHD);
const scratchRes = new Int32Array(PER_NBHD);

/** First k entries of a uniformly random permutation of `from` (partial Fisher–Yates). */
function drawWithoutReplacement(from: ArrayLike<number>, k: number, rng: () => number, scratch: Int32Array): Int32Array {
  const n = from.length;
  if (k > n) throw new Error(`cannot draw ${k} of ${n}`);
  // Reset the scratch every call, so a draw depends only on its seed.
  for (let i = 0; i < n; i++) scratch[i] = from[i];
  for (let i = 0; i < k; i++) {
    const j = i + Math.floor(rng() * (n - i));
    const t = scratch[i];
    scratch[i] = scratch[j];
    scratch[j] = t;
  }
  return scratch.slice(0, k).sort();
}

function finishSample(design: Sample['design'], seed: number, idx: Int32Array, piOf: (i: number) => number): Sample {
  const pop = getPopulation();
  const n = idx.length;
  const pi = new Float64Array(n);
  const d = new Float64Array(n);
  const cluster = new Uint16Array(n);
  const stratum = new Uint8Array(n);
  for (let k = 0; k < n; k++) {
    const i = idx[k];
    pi[k] = piOf(i);
    d[k] = 1 / pi[k];
    cluster[k] = pop.nbhd[i];
    stratum[k] = design === 'oversample' ? pop.g[i] : 0;
  }
  return { design, seed, n, idx, pi, d, cluster, stratum };
}

let identityPop: Int32Array | null = null;
let strataIdx: [Int32Array, Int32Array] | null = null;

/** Simple random sample of n adults without replacement: pi_i = n / N. */
export function srs(n: number, seed: number): Sample {
  if (!identityPop) identityPop = Int32Array.from({ length: N_POP }, (_, i) => i);
  const rng = mulberry32(deriveSeed('srs', seed, n));
  const idx = drawWithoutReplacement(identityPop, n, rng, scratchPop);
  return finishSample('srs', seed, idx, () => n / N_POP);
}

/**
 * Stratified SRS that selects members of G at `factorG` times the rate of everyone
 * else. Stratum sizes are n_G = round(n f N_G / (N_0 + f N_G)) and n_0 = n - n_G,
 * so pi_i = n_h / N_h exactly and sum_i pi_i = n.
 */
export function oversample(n: number, factorG: number, seed: number): Sample {
  const pop = getPopulation();
  if (!strataIdx) {
    const s0: number[] = [];
    const s1: number[] = [];
    for (let i = 0; i < N_POP; i++) (pop.g[i] ? s1 : s0).push(i);
    strataIdx = [Int32Array.from(s0), Int32Array.from(s1)];
  }
  const [s0, s1] = strataIdx;
  const N0 = s0.length;
  const N1 = s1.length;
  const n1 = Math.min(N1, n - 1, Math.max(1, Math.round((n * factorG * N1) / (N0 + factorG * N1))));
  const n0 = n - n1;
  const rng = mulberry32(deriveSeed('oversample', seed, n, factorG));
  const a = drawWithoutReplacement(s0, n0, rng, scratchPop);
  const b = drawWithoutReplacement(s1, n1, rng, scratchPop);
  const idx = new Int32Array(n);
  idx.set(a, 0);
  idx.set(b, n0);
  idx.sort();
  return finishSample('oversample', seed, idx, (i) => (pop.g[i] ? n1 / N1 : n0 / N0));
}

/** Two-stage cluster sample: SRS of m neighbourhoods, then SRS of k residents in each. */
export function clusterSample(m: number, k: number, seed: number): Sample {
  const rng = mulberry32(deriveSeed('cluster', seed, m, k));
  const nb = drawWithoutReplacement(Int32Array.from({ length: N_NBHD }, (_, j) => j), m, rng, scratchNbhd);
  const residents = Int32Array.from({ length: PER_NBHD }, (_, r) => r);
  const idx = new Int32Array(m * k);
  for (let c = 0; c < m; c++) {
    const r = drawWithoutReplacement(residents, k, rng, scratchRes);
    for (let t = 0; t < k; t++) idx[c * k + t] = nb[c] * PER_NBHD + r[t];
  }
  idx.sort();
  const pi = (m / N_NBHD) * (k / PER_NBHD);
  return finishSample('cluster', seed, idx, () => pi);
}

/** Unit nonresponse: each sampled adult responds with probability rho_i (age and college). */
export function nonresponse(sample: Sample, seed: number): RespondedSample {
  const pop = getPopulation();
  const rng = mulberry32(deriveSeed('nonresponse', seed, sample.design, sample.seed, sample.n));
  const responded = new Uint8Array(sample.n);
  const rho = new Float64Array(sample.n);
  for (let k = 0; k < sample.n; k++) {
    rho[k] = pop.rho[sample.idx[k]];
    responded[k] = rng() < rho[k] ? 1 : 0;
  }
  return { ...sample, responded, rho };
}

/** Values of a population array at the sampled indices. */
export function pick(values: ArrayLike<number>, idx: ArrayLike<number>): Float64Array {
  const out = new Float64Array(idx.length);
  for (let k = 0; k < idx.length; k++) out[k] = values[idx[k]];
  return out;
}

// ------------------------------------------------------------------ estimators

const sum = (a: ArrayLike<number>): number => {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i];
  return s;
};

/** Weighted (Hájek) mean sum(w y) / sum(w); the plain mean when w is omitted. */
export function weightedMean(y: ArrayLike<number>, w?: ArrayLike<number> | null): number {
  if (!w) return sum(y) / y.length;
  let sw = 0, swy = 0;
  for (let i = 0; i < y.length; i++) {
    sw += w[i];
    swy += w[i] * y[i];
  }
  return swy / sw;
}

/** Coefficient of variation of the weights, sd / mean with the 1/n variance. */
export function cv(w: ArrayLike<number>): number {
  const n = w.length;
  const m = sum(w) / n;
  let ss = 0;
  for (let i = 0; i < n; i++) ss += (w[i] - m) ** 2;
  return Math.sqrt(ss / n) / m;
}

/** Kish effective sample size n / (1 + CV(w)^2), identical to (sum w)^2 / sum w^2. */
export function kishN(w: ArrayLike<number>): number {
  return w.length / (1 + cv(w) ** 2);
}

export interface RakeResult {
  weights: Float64Array;
  iterations: number;
  converged: boolean;
  /** Largest relative gap between a weighted margin total and its target. */
  maxError: number;
  history: { iteration: number; maxError: number }[];
}

/**
 * Raking (iterative proportional fitting) to population totals. Each full
 * iteration scales the weights to match every margin in turn; it stops when the
 * largest relative margin error falls below `tol`.
 */
export function rake(
  sample: { idx: ArrayLike<number> },
  weights: ArrayLike<number>,
  margins: Margin[],
  opts: { maxIter?: number; tol?: number } = {},
): RakeResult {
  const maxIter = opts.maxIter ?? 100;
  const tol = opts.tol ?? 1e-10;
  const n = sample.idx.length;
  const w = Float64Array.from(weights);
  const cats = margins.map((m) => {
    const c = new Int32Array(n);
    for (let k = 0; k < n; k++) c[k] = m.of(sample.idx[k]);
    return c;
  });
  const totals = (mi: number): number[] => {
    const t = new Array<number>(margins[mi].targets.length).fill(0);
    const c = cats[mi];
    for (let k = 0; k < n; k++) t[c[k]] += w[k];
    return t;
  };
  const maxErr = (): number => {
    let e = 0;
    margins.forEach((m, mi) => {
      const t = totals(mi);
      m.targets.forEach((target, j) => {
        if (target > 0) e = Math.max(e, Math.abs(t[j] - target) / target);
      });
    });
    return e;
  };
  const history: RakeResult['history'] = [];
  let err = maxErr();
  let it = 0;
  while (err >= tol && it < maxIter) {
    it++;
    margins.forEach((m, mi) => {
      const t = totals(mi);
      const f = m.targets.map((target, j) => (t[j] > 0 ? target / t[j] : 1));
      const c = cats[mi];
      for (let k = 0; k < n; k++) w[k] *= f[c[k]];
    });
    err = maxErr();
    history.push({ iteration: it, maxError: err });
  }
  return { weights: w, iterations: it, converged: err < tol, maxError: err, history };
}

export interface TrimResult {
  weights: Float64Array;
  /** Units whose weight was capped. */
  trimmed: number;
  cap: number;
}

/**
 * Caps weights at `cap`. With `renormalize`, the trimmed excess is spread over
 * the untrimmed units in proportion to their weights, repeatedly, until no
 * weight exceeds the cap; the total is preserved.
 */
export function trim(weights: ArrayLike<number>, cap: number, opts: { renormalize?: boolean } = {}): TrimResult {
  const n = weights.length;
  const total = sum(weights);
  const c = opts.renormalize ? Math.max(cap, total / n) : cap;
  const w = Float64Array.from(weights);
  const capped = new Uint8Array(n);
  for (let pass = 0; pass < 100; pass++) {
    let any = false;
    for (let k = 0; k < n; k++) {
      if (w[k] > c * (1 + 1e-12)) {
        w[k] = c;
        capped[k] = 1;
        any = true;
      }
    }
    if (!opts.renormalize) break;
    let free = 0;
    let fixed = 0;
    for (let k = 0; k < n; k++) {
      if (capped[k]) fixed += w[k];
      else free += w[k];
    }
    if (free <= 0) break;
    const f = (total - fixed) / free;
    for (let k = 0; k < n; k++) if (!capped[k]) w[k] *= f;
    if (!any && Math.abs(f - 1) < 1e-14) break;
  }
  return { weights: w, trimmed: sum(capped), cap: c };
}

/** Naive iid SE of the unweighted mean: s / sqrt(n). */
export function seIID(y: ArrayLike<number>): number {
  const n = y.length;
  const m = sum(y) / n;
  let ss = 0;
  for (let i = 0; i < n; i++) ss += (y[i] - m) ** 2;
  return Math.sqrt(ss / (n - 1) / n);
}

/** Weights read as frequency weights f_i: as if sum(f) independent records were observed. */
export function seFrequency(y: ArrayLike<number>, f: ArrayLike<number>): number {
  const F = sum(f);
  const m = weightedMean(y, f);
  let ss = 0;
  for (let i = 0; i < y.length; i++) ss += f[i] * (y[i] - m) ** 2;
  return Math.sqrt(ss / (F - 1) / F);
}

/** Weights read as precision weights a_i (Var y_i = sigma^2 / a_i): sqrt(sum a (y - m)^2 / ((n - 1) sum a)). */
export function sePrecision(y: ArrayLike<number>, a: ArrayLike<number>): number {
  const m = weightedMean(y, a);
  let ss = 0;
  for (let i = 0; i < y.length; i++) ss += a[i] * (y[i] - m) ** 2;
  return Math.sqrt(ss / ((y.length - 1) * sum(a)));
}

/**
 * Weights read as sampling weights w_i, weights only (no strata or clusters):
 * with-replacement linearization, V = n/(n-1) sum (w_i (y_i - m))^2 / (sum w)^2.
 */
export function seLinearized(y: ArrayLike<number>, w: ArrayLike<number>): number {
  const n = y.length;
  const m = weightedMean(y, w);
  let ss = 0;
  for (let i = 0; i < n; i++) ss += (w[i] * (y[i] - m)) ** 2;
  return Math.sqrt((n / (n - 1)) * ss) / sum(w);
}

/**
 * Cluster-robust (linearized) SE of a weighted mean, clusters = neighbourhoods:
 * V = G/(G-1) sum_g (sum_{i in g} w_i (y_i - m))^2 / (sum w)^2. Ignores the
 * finite-population correction for sampled clusters.
 */
export function seCluster(y: ArrayLike<number>, w: ArrayLike<number> | null, cluster: ArrayLike<number>): number {
  const n = y.length;
  const m = weightedMean(y, w);
  const t = new Map<number, number>();
  let W = 0;
  for (let i = 0; i < n; i++) {
    const wi = w ? w[i] : 1;
    W += wi;
    t.set(cluster[i], (t.get(cluster[i]) ?? 0) + wi * (y[i] - m));
  }
  const G = t.size;
  let ss = 0;
  for (const v of t.values()) ss += v * v;
  return Math.sqrt((G / (G - 1)) * ss) / W;
}

export interface OlsCellStat {
  n: number;
  /** Treated share in the cell. */
  p: number;
  /** Treated-minus-untreated mean difference in the cell (NaN if one arm is empty). */
  tauHat: number;
  /** Implicit weight n_g p_g (1 - p_g) / sum, the Angrist variance weight. */
  omega: number;
}

export interface OlsCellsResult {
  beta: number;
  se: number;
  seHC1: number;
  cells: OlsCellStat[];
}

/**
 * OLS of y on a binary treatment d plus a full set of cell dummies (saturated
 * controls), in closed form by Frisch–Waugh–Lovell: beta = sum (d - dbar_g) y /
 * sum (d - dbar_g)^2 = sum_g omega_g tauHat_g, omega_g ∝ n_g p_g (1 - p_g).
 */
export function olsCells(y: ArrayLike<number>, d: ArrayLike<number>, cell: ArrayLike<number>, nCells: number): OlsCellsResult {
  const n = y.length;
  const cn = new Float64Array(nCells);
  const cd = new Float64Array(nCells);
  const cy = new Float64Array(nCells);
  const cy1 = new Float64Array(nCells);
  for (let i = 0; i < n; i++) {
    cn[cell[i]]++;
    cd[cell[i]] += d[i];
    cy[cell[i]] += y[i];
    if (d[i]) cy1[cell[i]] += y[i];
  }
  let sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) {
    const dt = d[i] - cd[cell[i]] / cn[cell[i]];
    sxy += dt * y[i];
    sxx += dt * dt;
  }
  const beta = sxy / sxx;
  let see = 0, meat = 0;
  for (let i = 0; i < n; i++) {
    const c = cell[i];
    const dt = d[i] - cd[c] / cn[c];
    const e = y[i] - cy[c] / cn[c] - beta * dt;
    see += e * e;
    meat += dt * dt * e * e;
  }
  let used = 0;
  for (let c = 0; c < nCells; c++) if (cn[c] > 0) used++;
  const kParams = used + 1;
  const se = Math.sqrt(see / (n - kParams) / sxx);
  const seHC1 = Math.sqrt((meat / (sxx * sxx)) * (n / (n - kParams)));
  const cells: OlsCellStat[] = [];
  for (let c = 0; c < nCells; c++) {
    const nc = cn[c];
    const p = nc > 0 ? cd[c] / nc : NaN;
    const n1 = cd[c];
    const n0 = nc - n1;
    const tauHat = n1 > 0 && n0 > 0 ? cy1[c] / n1 - (cy[c] - cy1[c]) / n0 : NaN;
    cells.push({ n: nc, p, tauHat, omega: nc > 0 ? (nc * p * (1 - p)) / sxx : 0 });
  }
  return { beta, se, seHC1, cells };
}

export interface EffectCell {
  share: number;
  p: number;
  tau: number;
}

export interface EffectAverages {
  /** Implicit regression weights omega_g ∝ share_g p_g (1 - p_g), summing to 1. */
  omega: number[];
  /** sum_g omega_g tau_g: what OLS with saturated cell controls targets. */
  regression: number;
  /** Population-share weighted (PATE-analogue). */
  pate: number;
  /** Treated-share weighted (ATT-analogue). */
  att: number;
  /** Untreated-share weighted (ATU-analogue). */
  atu: number;
}

/** The Angrist (1998) variance-weight formula and the three population averages. */
export function angristWeights(cells: EffectCell[]): EffectAverages {
  const v = cells.map((c) => c.share * c.p * (1 - c.p));
  const V = v.reduce((a, b) => a + b, 0);
  const omega = v.map((x) => (V > 0 ? x / V : 0));
  const wavg = (w: number[]) => {
    const s = w.reduce((a, b) => a + b, 0);
    return s > 0 ? w.reduce((acc, wi, g) => acc + wi * cells[g].tau, 0) / s : NaN;
  };
  return {
    omega,
    regression: V > 0 ? omega.reduce((acc, o, g) => acc + o * cells[g].tau, 0) : NaN,
    pate: wavg(cells.map((c) => c.share)),
    att: wavg(cells.map((c) => c.share * c.p)),
    atu: wavg(cells.map((c) => c.share * (1 - c.p))),
  };
}

/**
 * Two groups: plim of the OLS coefficient with a group dummy,
 * (pi p1(1-p1) tau1 + (1-pi) p0(1-p0) tau0) / (pi p1(1-p1) + (1-pi) p0(1-p0)).
 */
export function twoGroupPlim(a: { pi: number; p1: number; p0: number; tau1: number; tau0: number }) {
  const r = angristWeights([
    { share: a.pi, p: a.p1, tau: a.tau1 },
    { share: 1 - a.pi, p: a.p0, tau: a.tau0 },
  ]);
  const v1 = a.p1 * (1 - a.p1);
  const v0 = a.p0 * (1 - a.p0);
  return {
    ...r,
    ols: r.regression,
    weight1: r.omega[0],
    equalEffects: Math.abs(a.tau1 - a.tau0) < 1e-9,
    equalVariance: Math.abs(v1 - v0) < 1e-9,
  };
}

// ------------------------------------------------------------------ widget helpers

/** Weighting-class nonresponse adjustment within age x college cells, for the respondents. */
export function weightingClassAdjust(s: RespondedSample): { resp: Int32Array; weights: Float64Array } {
  const pop = getPopulation();
  const all = new Float64Array(N_CELLS);
  const rsp = new Float64Array(N_CELLS);
  const pos: number[] = [];
  for (let k = 0; k < s.n; k++) {
    const c = pop.cell[s.idx[k]];
    all[c] += s.d[k];
    if (s.responded[k]) {
      rsp[c] += s.d[k];
      pos.push(k);
    }
  }
  const resp = Int32Array.from(pos, (k) => s.idx[k]);
  const weights = Float64Array.from(pos, (k) => {
    const c = pop.cell[s.idx[k]];
    return s.d[k] * (all[c] / rsp[c]);
  });
  return { resp, weights };
}

export type StageKey = 'unweighted' | 'design' | 'nonresponse' | 'raked' | 'trimmed' | 'final';

export interface StageResult {
  key: StageKey;
  weights: Float64Array;
  estimate: number;
  cv: number;
  kishN: number;
  /** Weights-only linearized SE. */
  se: number;
  total: number;
  maxRatio: number;
}

export interface PipelineResult {
  stages: StageResult[];
  /** Respondents' population indices and outcome. */
  resp: Int32Array;
  y: Float64Array;
  rake: RakeResult;
  trim: TrimResult;
  reRake: RakeResult;
  /** Largest relative margin error after trimming, before re-raking. */
  trimMarginError: number;
}

/** The Chapter 2 pipeline: design weights -> nonresponse -> raking -> trimming -> re-raking. */
export function weightPipeline(s: RespondedSample, capMultiple: number): PipelineResult {
  const pop = getPopulation();
  const margins = [pop.margins.ageCollege, pop.margins.g];
  const { resp, weights: nr } = weightingClassAdjust(s);
  const y = pick(pop.uninsured, resp);
  const design = new Float64Array(resp.length);
  let r = 0;
  for (let k = 0; k < s.n; k++) if (s.responded[k]) design[r++] = s.d[k];
  const unit = { idx: resp };
  const raked = rake(unit, nr, margins);
  const mean = sum(raked.weights) / raked.weights.length;
  const trimmed = trim(raked.weights, capMultiple * mean, { renormalize: true });
  const check = rake(unit, trimmed.weights, margins, { maxIter: 0 });
  const reRake = rake(unit, trimmed.weights, margins);
  const stage = (key: StageKey, w: Float64Array): StageResult => {
    let mx = 0;
    const m = sum(w) / w.length;
    for (let k = 0; k < w.length; k++) mx = Math.max(mx, w[k] / m);
    return { key, weights: w, estimate: weightedMean(y, w), cv: cv(w), kishN: kishN(w), se: seLinearized(y, w), total: sum(w), maxRatio: mx };
  };
  return {
    stages: [
      stage('unweighted', new Float64Array(resp.length).fill(1)),
      stage('design', design),
      stage('nonresponse', nr),
      stage('raked', raked.weights),
      stage('trimmed', trimmed.weights),
      stage('final', reRake.weights),
    ],
    resp,
    y,
    rake: raked,
    trim: trimmed,
    reRake,
    trimMarginError: check.maxError,
  };
}

export interface DesignSim {
  n: number;
  k: number;
  m: number;
  reps: number;
  srs: { est: Float64Array; naive: Float64Array };
  cluster: { est: Float64Array; naive: Float64Array; robust: Float64Array };
  /** SE of the mean under SRS without replacement, from the population (with FPC). */
  srsTrueSE: number;
}

/** Repeated SRS and two-stage cluster samples of the same size, scoring the mean of `uninsured`. */
export function simulateDesigns(o: { n: number; k: number; reps: number; seed: number }): DesignSim {
  const pop = getPopulation();
  const m = Math.round(o.n / o.k);
  const sim: DesignSim = {
    n: o.n, k: o.k, m, reps: o.reps,
    srs: { est: new Float64Array(o.reps), naive: new Float64Array(o.reps) },
    cluster: { est: new Float64Array(o.reps), naive: new Float64Array(o.reps), robust: new Float64Array(o.reps) },
    srsTrueSE: 0,
  };
  for (let r = 0; r < o.reps; r++) {
    const s1 = srs(o.n, deriveSeed(o.seed, 'rep', r));
    const y1 = pick(pop.uninsured, s1.idx);
    sim.srs.est[r] = weightedMean(y1);
    sim.srs.naive[r] = seIID(y1);
    const s2 = clusterSample(m, o.k, deriveSeed(o.seed, 'rep', r));
    const y2 = pick(pop.uninsured, s2.idx);
    sim.cluster.est[r] = weightedMean(y2);
    sim.cluster.naive[r] = seIID(y2);
    sim.cluster.robust[r] = seCluster(y2, null, s2.cluster);
  }
  const P = pop.truths.prevalence;
  const N = pop.N;
  // Exact SRSWOR variance of a mean of a 0/1 variable: P(1 - P)/n * (N - n)/(N - 1).
  sim.srsTrueSE = Math.sqrt(((P * (1 - P)) / o.n) * ((N - o.n) / (N - 1)));
  return sim;
}

export interface ScenarioCell {
  label: string;
  share: number;
  /** Realized treated share in the population under the scenario. */
  p: number;
  tau: number;
  omega: number;
}

export interface WfhScenario {
  het: number;
  spread: number;
  d: Uint8Array;
  cellTau: number[];
  cells: ScenarioCell[];
  pate: number;
  att: number;
  atu: number;
  /** sum_g omega_g tau_g with omega_g ∝ share_g p_g (1 - p_g): the target of OLS with cell dummies. */
  olsTarget: number;
  treatedShare: number;
}

/**
 * The Chapter 0 regression scenario. `het` scales every cell effect's distance
 * from the baseline PATE (0 = homogeneous effects, 1 = baseline); `spread`
 * scales each cell's treatment log-odds away from the overall rate (0 = equal
 * rates, full overlap; 1 = baseline). Treatment is redrawn with each resident's
 * fixed uniform, so a scenario changes rates, not people.
 */
export function wfhScenario(het: number, spread: number): WfhScenario {
  const pop = getPopulation();
  const T = pop.truths;
  const P = SYNTHPOP_PARAMS;
  const m = T.pate;
  const pModel = Array.from({ length: N_CELLS }, (_, c) => P.wfhP[c >= 3 ? 1 : 0][c % 3]);
  const pBar = pModel.reduce((a, p, c) => a + p * T.cellShares[c], 0);
  const pS = pModel.map((p) => expit(logit(pBar) + spread * (logit(p) - logit(pBar))));
  const cellTau = T.cellTau.map((t) => m + het * (t - m));
  const d = new Uint8Array(pop.N);
  const n1 = new Array<number>(N_CELLS).fill(0);
  for (let i = 0; i < pop.N; i++) {
    d[i] = pop.uWfh[i] < pS[pop.cell[i]] ? 1 : 0;
    n1[pop.cell[i]] += d[i];
  }
  const cells: EffectCell[] = T.cellShares.map((share, c) => ({ share, p: n1[c] / (share * pop.N), tau: cellTau[c] }));
  const avg = angristWeights(cells);
  const treated = n1.reduce((a, b) => a + b, 0);
  return {
    het, spread, d, cellTau,
    cells: cells.map((c, g) => ({ label: CELL_LABELS[g], share: c.share, p: c.p, tau: c.tau, omega: avg.omega[g] })),
    pate: avg.pate,
    att: avg.att,
    atu: avg.atu,
    olsTarget: avg.regression,
    treatedShare: treated / pop.N,
  };
}

/** OLS of logwage on wfh + cell dummies in one SRS under a scenario. */
export function scenarioSampleOLS(scn: WfhScenario, n: number, seed: number): OlsCellsResult {
  const pop = getPopulation();
  const s = srs(n, seed);
  const y = new Float64Array(n);
  const d = new Uint8Array(n);
  const cell = new Uint8Array(n);
  for (let k = 0; k < n; k++) {
    const i = s.idx[k];
    d[k] = scn.d[i];
    cell[k] = pop.cell[i];
    y[k] = pop.base[i] + scn.cellTau[cell[k]] * d[k];
  }
  return olsCells(y, d, cell, N_CELLS);
}
