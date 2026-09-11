/**
 * Run: node --import tsx --test lib/synthpop.test.ts
 *
 * Checks every mathematical claim the synthetic widgets display (v3 section 11.2):
 * raking, Kish, Hájek unbiasedness under oversampling, the Angrist
 * variance-weight identity for OLS with saturated cell dummies, and the design
 * effect of cluster sampling. Monte Carlo checks are seeded and deterministic.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  SYNTHPOP_VERSION,
  SYNTHPOP_SEED,
  N_POP,
  N_NBHD,
  PER_NBHD,
  N_CELLS,
  getPopulation,
  srs,
  oversample,
  clusterSample,
  nonresponse,
  pick,
  weightedMean,
  cv,
  kishN,
  rake,
  trim,
  seIID,
  seFrequency,
  sePrecision,
  seLinearized,
  seCluster,
  olsCells,
  angristWeights,
  twoGroupPlim,
  weightingClassAdjust,
  weightPipeline,
  wfhScenario,
  deriveSeed,
} from './synthpop';

const pop = getPopulation();
const T = pop.truths;
const total = (a: ArrayLike<number>) => {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i];
  return s;
};
const meanSd = (a: number[]) => {
  const m = a.reduce((x, y) => x + y, 0) / a.length;
  const sd = Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1));
  return { m, sd };
};

test('version, seed, and shape', () => {
  assert.equal(SYNTHPOP_VERSION, '1.0.0');
  assert.equal(SYNTHPOP_SEED, 20260910);
  assert.equal(pop.N, N_POP);
  assert.equal(N_POP, 20000);
  const perNbhd = new Array<number>(N_NBHD).fill(0);
  for (let i = 0; i < pop.N; i++) perNbhd[pop.nbhd[i]]++;
  assert.ok(perNbhd.every((c) => c === PER_NBHD));
  assert.equal(total(pop.nbhdRural), 60);
});

test('population is reproducible: pinned fingerprint for version 1.0.0', () => {
  assert.equal(total(pop.uninsured), 2477);
  assert.equal(total(pop.wfh), 2922);
  assert.equal(total(pop.g), 3040);
  assert.equal(total(pop.college), 6925);
  assert.equal(total(pop.logwage).toFixed(3), '68595.149');
});

test('calibrated shares, and truths computed from the population', () => {
  assert.ok(Math.abs(T.prevalence - 0.12) < 0.01);
  assert.ok(Math.abs(T.gShare - 0.15) < 0.015);
  assert.ok(Math.abs(T.collegeShare - 0.35) < 0.015);
  [0.34, 0.35, 0.31].forEach((s, a) => assert.ok(Math.abs(T.ageShares[a] - s) < 0.015));
  assert.ok(Math.abs(T.wfhShareCollege - 0.3) < 0.02);
  assert.ok(Math.abs(T.wfhShareNoDegree - 0.06) < 0.01);
  assert.ok(Math.abs(T.pate - total(pop.tau) / pop.N) < 1e-12);
  assert.ok(T.att > T.pate && T.pate > T.atu);
  // G is concentrated in high-u neighbourhoods.
  const share = Array.from({ length: N_NBHD }, (_, j) => total(pop.g.subarray(j * PER_NBHD, (j + 1) * PER_NBHD)) / PER_NBHD);
  const u = Array.from(pop.nbhdU);
  const a = meanSd(share);
  const b = meanSd(u);
  const r = share.reduce((acc, s, j) => acc + (s - a.m) * (u[j] - b.m), 0) / ((N_NBHD - 1) * a.sd * b.sd);
  assert.ok(r > 0.4, `corr(G share, u) = ${r}`);
});

test('samples carry exact inclusion probabilities and are reproducible', () => {
  // sum over the population of pi_i is n; over the sample, sum d_i = N.
  const s = srs(500, 7);
  assert.equal(new Set(s.idx).size, 500);
  assert.ok(Math.abs(total(s.d) - N_POP) < 1e-6);
  assert.ok(Math.abs(s.pi[0] * N_POP - 500) < 1e-9);
  assert.deepEqual(Array.from(srs(500, 7).idx), Array.from(s.idx));
  assert.notDeepEqual(Array.from(srs(500, 8).idx), Array.from(s.idx));

  const o = oversample(1000, 4, 3);
  assert.equal(new Set(o.idx).size, 1000);
  assert.ok(Math.abs(total(o.d) - N_POP) < 1e-6);
  // pi_i = n_h / N_h exactly, so the design weights of each stratum sum to N_h.
  let dG = 0;
  let d0 = 0;
  for (let k = 0; k < o.n; k++) {
    if (pop.g[o.idx[k]]) dG += o.d[k];
    else d0 += o.d[k];
  }
  assert.ok(Math.abs(dG - T.gShare * N_POP) < 1e-6);
  assert.ok(Math.abs(d0 - (1 - T.gShare) * N_POP) < 1e-6);
  const piG = o.pi[o.idx.findIndex((i) => pop.g[i] === 1)];
  const pi0 = o.pi[o.idx.findIndex((i) => pop.g[i] === 0)];
  assert.ok(Math.abs(piG / pi0 - 4) < 0.05);

  const c = clusterSample(25, 40, 9);
  assert.equal(c.n, 1000);
  assert.equal(new Set(c.cluster).size, 25);
  assert.ok(Array.from(c.pi).every((p) => Math.abs(p - (25 / 200) * (40 / 100)) < 1e-15));
});

test('raking reproduces the margins within 1e-6', () => {
  const margins = [pop.margins.ageCollege, pop.margins.g];
  const s = nonresponse(oversample(2000, 4, 11), 11);
  const { resp, weights } = weightingClassAdjust(s);
  for (const start of [weights, new Float64Array(resp.length).fill(1)]) {
    const r = rake({ idx: resp }, start, margins, { tol: 1e-12, maxIter: 500 });
    assert.ok(r.converged, `not converged after ${r.iterations}`);
    const W = total(r.weights);
    for (const m of margins) {
      const t = new Array<number>(m.targets.length).fill(0);
      resp.forEach((i, k) => (t[m.of(i)] += r.weights[k]));
      m.targets.forEach((target, j) => {
        assert.ok(Math.abs(t[j] - target) / target < 1e-6, `${m.name}[${j}]: ${t[j]} vs ${target}`);
        assert.ok(Math.abs(t[j] / W - target / N_POP) < 1e-6);
      });
    }
  }
});

test('kishN = n / (1 + CV^2) = (sum w)^2 / sum w^2', () => {
  assert.equal(kishN([2, 2, 2, 2]), 4);
  assert.ok(Math.abs(kishN([1, 2, 3, 4]) - 100 / 30) < 1e-12);
  const w = oversample(1000, 6, 2).d;
  const direct = total(w) ** 2 / total(Array.from(w, (x) => x * x));
  assert.ok(Math.abs(kishN(w) - direct) < 1e-9);
  assert.ok(Math.abs(kishN(w) - w.length / (1 + cv(w) ** 2)) < 1e-9);
  assert.ok(kishN(w) < w.length);
});

test('trim caps the weights and, renormalised, preserves the total', () => {
  const w = [1, 1, 1, 1, 10];
  const plain = trim(w, 4);
  assert.deepEqual(Array.from(plain.weights), [1, 1, 1, 1, 4]);
  assert.equal(plain.trimmed, 1);
  const re = trim(w, 4, { renormalize: true });
  assert.ok(Math.abs(total(re.weights) - 14) < 1e-9);
  assert.ok(Math.max(...re.weights) <= 4 + 1e-9);
});

test('the Hájek mean is unbiased for the population mean under oversampling (400 draws)', () => {
  const R = 400;
  const hajek: number[] = [];
  const naive: number[] = [];
  for (let r = 0; r < R; r++) {
    const s = oversample(1000, 4, deriveSeed('test-hajek', r));
    const y = pick(pop.uninsured, s.idx);
    hajek.push(weightedMean(y, s.d));
    naive.push(weightedMean(y));
  }
  const h = meanSd(hajek);
  const bias = h.m - T.prevalence;
  const mcse = h.sd / Math.sqrt(R);
  assert.ok(Math.abs(bias) < 3 * mcse, `bias ${bias}, MC SE ${mcse}`);
  // The unweighted mean is not: G is oversampled and more often uninsured.
  const u = meanSd(naive);
  assert.ok(u.m - T.prevalence > 3 * (u.sd / Math.sqrt(R)));
});

/** Solves A x = b by Gaussian elimination with partial pivoting (independent of olsCells). */
function solve(A: number[][], b: number[]): number[] {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((row, i) => row[n] / row[i]);
}

test('OLS with saturated cell dummies equals sum_g omega_g tauHat_g, omega_g ∝ n_g p_g (1 - p_g)', () => {
  const s = srs(3000, 5);
  const y = pick(pop.logwage, s.idx);
  const d = pick(pop.wfh, s.idx);
  const cell = pick(pop.cell, s.idx);
  // Generic OLS: X = [d, six cell dummies], normal equations.
  const K = 1 + N_CELLS;
  const XtX = Array.from({ length: K }, () => new Array<number>(K).fill(0));
  const Xty = new Array<number>(K).fill(0);
  for (let i = 0; i < y.length; i++) {
    const x = new Array<number>(K).fill(0);
    x[0] = d[i];
    x[1 + cell[i]] = 1;
    for (let a = 0; a < K; a++) {
      Xty[a] += x[a] * y[i];
      for (let b = 0; b < K; b++) XtX[a][b] += x[a] * x[b];
    }
  }
  const betaGeneric = solve(XtX, Xty)[0];
  // Cell by cell, by hand.
  let num = 0;
  let den = 0;
  const cells = [];
  for (let g = 0; g < N_CELLS; g++) {
    let n = 0, n1 = 0, s1 = 0, s0 = 0;
    for (let i = 0; i < y.length; i++) {
      if (cell[i] !== g) continue;
      n++;
      if (d[i]) { n1++; s1 += y[i]; } else s0 += y[i];
    }
    const p = n1 / n;
    const tauHat = s1 / n1 - s0 / (n - n1);
    num += n * p * (1 - p) * tauHat;
    den += n * p * (1 - p);
    cells.push({ share: n / y.length, p, tau: tauHat });
  }
  const angrist = num / den;
  assert.ok(Math.abs(betaGeneric - angrist) < 1e-10, `${betaGeneric} vs ${angrist}`);
  assert.ok(Math.abs(olsCells(y, d, cell, N_CELLS).beta - betaGeneric) < 1e-10);
  assert.ok(Math.abs(angristWeights(cells).regression - betaGeneric) < 1e-10);
});

test('under cluster sampling the naive SE understates the Monte Carlo SD (design effect > 1)', () => {
  const R = 400;
  const est: number[] = [];
  const naive: number[] = [];
  const robust: number[] = [];
  for (let r = 0; r < R; r++) {
    const s = clusterSample(25, 40, deriveSeed('test-cluster', r));
    const y = pick(pop.uninsured, s.idx);
    est.push(weightedMean(y));
    naive.push(seIID(y));
    robust.push(seCluster(y, null, s.cluster));
  }
  const { sd } = meanSd(est);
  const naiveSE = meanSd(naive).m;
  const deff = (sd / naiveSE) ** 2;
  assert.ok(deff > 1.3, `design effect ${deff}`);
  // The cluster-robust SE tracks the actual spread (within 20%).
  assert.ok(Math.abs(meanSd(robust).m / sd - 1) < 0.2);
});

test('one weight vector read three ways: one mean, three standard errors', () => {
  const p = weightPipeline(nonresponse(oversample(2000, 4, 21), 21), 2);
  const w = p.stages[p.stages.length - 1].weights;
  const y = p.y;
  const se = [seFrequency(y, w), sePrecision(y, w), seLinearized(y, w)];
  assert.ok(se[0] < se[1] && se[0] < se[2]);
  assert.ok(new Set(se.map((x) => x.toFixed(6))).size === 3);
  // With equal weights all three collapse to the iid SE.
  const ones = new Float64Array(y.length).fill(1);
  for (const f of [seFrequency, sePrecision, seLinearized]) assert.ok(Math.abs(f(y, ones) - seIID(y)) < 1e-12);
});

test('two-group plim formula and its knife-edge cases', () => {
  const a = { pi: 0.35, p1: 0.3, p0: 0.06, tau1: 0.2, tau0: 0.04 };
  const r = twoGroupPlim(a);
  const v1 = a.pi * a.p1 * (1 - a.p1);
  const v0 = (1 - a.pi) * a.p0 * (1 - a.p0);
  assert.ok(Math.abs(r.ols - (v1 * a.tau1 + v0 * a.tau0) / (v1 + v0)) < 1e-15);
  assert.ok(Math.abs(r.pate - (a.pi * a.tau1 + (1 - a.pi) * a.tau0)) < 1e-15);
  const same = twoGroupPlim({ ...a, tau0: a.tau1 });
  assert.ok(same.equalEffects && Math.abs(same.ols - same.pate) < 1e-15 && Math.abs(same.att - same.atu) < 1e-15);
  const mirror = twoGroupPlim({ ...a, p0: 1 - a.p1 });
  assert.ok(mirror.equalVariance && Math.abs(mirror.ols - mirror.pate) < 1e-12);
});

test('regression scenario: homogeneous effects or equal treatment rates put the OLS target on the PATE', () => {
  const base = wfhScenario(1, 1);
  assert.ok(Math.abs(base.pate - T.pate) < 1e-12);
  assert.ok(Math.abs(base.att - T.att) < 1e-12);
  assert.ok(base.olsTarget - base.pate > 0.03);
  const flat = wfhScenario(0, 1);
  assert.ok(Math.abs(flat.olsTarget - flat.pate) < 1e-12);
  const overlap = wfhScenario(1, 0);
  // Equal model rates: realized rates differ only by chance, so the gap nearly vanishes.
  assert.ok(Math.abs(overlap.olsTarget - overlap.pate) < 0.005);
});
