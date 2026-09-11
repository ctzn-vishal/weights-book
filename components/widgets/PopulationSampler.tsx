'use client';

/**
 * Chapter 0 hero: one synthetic population, three stages, one idea active at a
 * time. (1) who enters the sample moves representation; (2) how the sample is
 * drawn moves uncertainty; (3) effect heterogeneity and overlap move the
 * regression target. Every number is computed live from lib/synthpop.ts.
 */

import { useMemo, useState } from 'react';
import {
  N_POP,
  SYNTHPOP_SEED,
  SYNTHPOP_VERSION,
  deriveSeed,
  getPopulation,
  oversample,
  pick,
  scenarioSampleOLS,
  simulateDesigns,
  weightedMean,
  wfhScenario,
} from '@/lib/synthpop';
import {
  DotRows,
  HeldFixed,
  Histogram,
  Note,
  SeedControl,
  Segmented,
  Slider,
  Swatch,
  WidgetFrame,
  binValues,
  buttonClass,
} from './ui';
import { fmt } from './format';

type Stage = '1' | '2' | '3';
const SAMPLE_N = 1000;
const REPS = 200;
/** SE or SD of a proportion in percentage points. */
const ppt = (v: number, d = 2) => `${(v * 100).toFixed(d)} pts`;
const mean = (a: ArrayLike<number>) => {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i];
  return s / a.length;
};
const sd = (a: ArrayLike<number>) => {
  const m = mean(a);
  let s = 0;
  for (let i = 0; i < a.length; i++) s += (a[i] - m) ** 2;
  return Math.sqrt(s / (a.length - 1));
};

export function PopulationSampler() {
  const [stage, setStage] = useState<Stage>('1');
  const [factor, setFactor] = useState(4);
  const [seed1, setSeed1] = useState(1);
  const [k, setK] = useState<'10' | '20' | '40' | '100'>('40');
  const [seed2, setSeed2] = useState(1);
  const [het, setHet] = useState(1);
  const [spread, setSpread] = useState(1);
  const [seed3, setSeed3] = useState(1);
  const next: Record<Stage, Stage | null> = { '1': '2', '2': '3', '3': null };

  return (
    <WidgetFrame
      title="One population, three questions"
      subtitle={`A synthetic population of ${fmt(N_POP, 'int')} adults in 200 neighbourhoods (version ${SYNTHPOP_VERSION}, population seed ${SYNTHPOP_SEED}). Each stage changes one thing.`}
    >
      <Segmented<Stage>
        legend="Stage"
        value={stage}
        onChange={setStage}
        options={[
          { value: '1', label: '1. Who enters the sample' },
          { value: '2', label: '2. How the sample was drawn' },
          { value: '3', label: '3. What the regression targets' },
        ]}
      />
      <div className="mt-4">
        {stage === '1' ? <Representation factor={factor} setFactor={setFactor} seed={seed1} setSeed={setSeed1} /> : null}
        {stage === '2' ? <Design k={k} setK={setK} seed={seed2} setSeed={setSeed2} /> : null}
        {stage === '3' ? (
          <Target het={het} setHet={setHet} spread={spread} setSpread={setSpread} seed={seed3} setSeed={setSeed3} />
        ) : null}
      </div>
      {next[stage] ? (
        <div className="mt-4 flex justify-end">
          <button type="button" className={buttonClass} onClick={() => setStage(next[stage]!)}>
            Next stage →
          </button>
        </div>
      ) : null}
    </WidgetFrame>
  );
}

// ------------------------------------------------------------------ stage 1

function Representation({
  factor,
  setFactor,
  seed,
  setSeed,
}: {
  factor: number;
  setFactor: (v: number) => void;
  seed: number;
  setSeed: (f: (s: number) => number) => void;
}) {
  const T = getPopulation().truths;
  const one = useMemo(() => {
    const pop = getPopulation();
    const s = oversample(SAMPLE_N, factor, seed);
    const y = pick(pop.uninsured, s.idx);
    const g = pick(pop.g, s.idx);
    const piG = s.pi[g.indexOf(1)];
    const pi0 = s.pi[g.indexOf(0)];
    return { unweighted: weightedMean(y), weighted: weightedMean(y, s.d), gShare: mean(g), piG, pi0 };
  }, [factor, seed]);
  const many = useMemo(() => {
    const pop = getPopulation();
    let u = 0;
    let w = 0;
    for (let r = 0; r < REPS; r++) {
      const s = oversample(SAMPLE_N, factor, deriveSeed('sampler-stage1', seed, r));
      const y = pick(pop.uninsured, s.idx);
      u += weightedMean(y);
      w += weightedMean(y, s.d);
    }
    return { unweighted: u / REPS, weighted: w / REPS };
  }, [factor, seed]);

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Slider
          label="How much more likely a member of group G is to be sampled"
          min={1}
          max={8}
          step={1}
          value={factor}
          onChange={setFactor}
          display={`${factor}×`}
          hint={`Selection probability: ${fmt(one.piG, 'pct1')} for G, ${fmt(one.pi0, 'pct1')} for everyone else. Design weight d = 1/π.`}
        />
        <SeedControl seed={seed} onNext={() => setSeed((s) => s + 1)} note={`n = ${fmt(SAMPLE_N, 'int')}`} />
      </div>

      <div className="mt-4 space-y-1.5" role="group" aria-label="Share of group G in the population and in the sample">
        {[
          { label: 'Population', share: T.gShare },
          { label: 'This sample', share: one.gShare },
        ].map((row) => (
          <div key={row.label} className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-center gap-2">
            <span className="text-ink-2">{row.label}</span>
            <div className="flex h-5 overflow-hidden rounded-sm border border-rule text-xs" aria-label={`${row.label}: ${fmt(row.share, 'pct0')} in group G`}>
              <div
                className="flex items-center whitespace-nowrap bg-[var(--role-design)] px-1 font-semibold text-[var(--surface)]"
                style={{ width: `${row.share * 100}%` }}
              >
                G {fmt(row.share, 'pct0')}
              </div>
              <div className="flex flex-1 items-center justify-end bg-sunken px-1 text-ink-2">not G</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4">
        <DotRows
          ariaLabel={`Uninsured rate: unweighted ${fmt(one.unweighted, 'pct1')}, weighted ${fmt(one.weighted, 'pct1')}, population truth ${fmt(T.prevalence, 'pct1')}.`}
          domain={[0.06, 0.24]}
          tickFormat={(v) => fmt(v, 'pct0')}
          reference={{ value: T.prevalence, label: `Simulated population truth ${fmt(T.prevalence, 'pct1')}` }}
          rows={[
            { key: 'u', label: 'Unweighted mean', value: one.unweighted, valueText: fmt(one.unweighted, 'pct1'), color: 'var(--role-unweighted)', hollow: true, shape: 'circle' },
            { key: 'w', label: 'Weighted (Hájek) mean', value: one.weighted, valueText: fmt(one.weighted, 'pct1'), color: 'var(--role-weighted)', shape: 'diamond', strong: true },
          ]}
        />
      </div>
      <p className="mt-2" aria-live="polite">
        Across {REPS} samples at this setting the unweighted mean averages{' '}
        <span className="font-semibold tabular-nums">{fmt(many.unweighted, 'pct1')}</span> and the weighted mean{' '}
        <span className="font-semibold tabular-nums">{fmt(many.weighted, 'pct1')}</span>, against a truth of{' '}
        {fmt(T.prevalence, 'pct1')}. Members of G are uninsured more often ({fmt(T.prevalenceG, 'pct0')} against{' '}
        {fmt(T.prevalenceNonG, 'pct0')}), so a sample that over-represents them overstates the rate unless each person
        counts 1/π times.
      </p>
      <HeldFixed>
        The population, the outcome (uninsured), and the sample size. Only who is likely to enter the sample changes; the
        design weights d = 1/π undo exactly that.
      </HeldFixed>
    </div>
  );
}

// ------------------------------------------------------------------ stage 2

function Design({
  k,
  setK,
  seed,
  setSeed,
}: {
  k: '10' | '20' | '40' | '100';
  setK: (v: '10' | '20' | '40' | '100') => void;
  seed: number;
  setSeed: (f: (s: number) => number) => void;
}) {
  const T = getPopulation().truths;
  const kk = Number(k);
  const sim = useMemo(() => simulateDesigns({ n: SAMPLE_N, k: kk, reps: REPS, seed: deriveSeed('sampler-stage2', seed) }), [kk, seed]);
  const domain: [number, number] = [0.04, 0.21];
  const srsBins = binValues(sim.srs.est, domain, 34);
  const clBins = binValues(sim.cluster.est, domain, 34);
  const yMax = Math.max(...srsBins.map((b) => b.count), ...clBins.map((b) => b.count));
  const srsSD = sd(sim.srs.est);
  const clSD = sd(sim.cluster.est);
  const deff = (clSD / sim.srsTrueSE) ** 2;
  const truthMark = [{ value: T.prevalence, label: `Truth ${fmt(T.prevalence, 'pct1')}` }];

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Segmented<'10' | '20' | '40' | '100'>
          legend={`Cluster sample of ${fmt(SAMPLE_N, 'int')}: neighbourhoods × residents in each`}
          value={k}
          onChange={setK}
          options={[
            { value: '10', label: '100 × 10' },
            { value: '20', label: '50 × 20' },
            { value: '40', label: '25 × 40' },
            { value: '100', label: '10 × 100' },
          ]}
        />
        <SeedControl seed={seed} onNext={() => setSeed((s) => s + 1)} label={`Draw ${REPS} new samples`} note={`${REPS} of each design`} />
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Histogram
          title={`Simple random samples of ${fmt(SAMPLE_N, 'int')}`}
          bins={srsBins}
          yMax={yMax}
          tickFormat={(v) => fmt(v, 'pct0')}
          markers={truthMark}
          color="var(--role-weighted)"
          ariaLabel={`Histogram of ${REPS} SRS estimates of the uninsured rate; standard deviation ${ppt(srsSD)}.`}
        />
        <Histogram
          title={`Cluster samples: ${sim.m} neighbourhoods × ${kk} residents`}
          bins={clBins}
          yMax={yMax}
          tickFormat={(v) => fmt(v, 'pct0')}
          markers={truthMark}
          color="var(--role-design)"
          ariaLabel={`Histogram of ${REPS} cluster-sample estimates of the uninsured rate; standard deviation ${ppt(clSD)}.`}
        />
      </div>
      <div className="mt-3 overflow-x-auto [contain:inline-size]">
        <table className="w-full min-w-[28rem] border-collapse text-sm tabular-nums [&_td]:border-b [&_td]:border-rule [&_td]:px-2 [&_td]:py-1 [&_th]:px-2 [&_th]:py-1">
          <thead>
            <tr className="border-b border-[var(--border-strong)]">
              <th scope="col" className="text-left font-semibold">Across {REPS} samples</th>
              <th scope="col" className="text-right font-semibold">Simple random</th>
              <th scope="col" className="text-right font-semibold">Cluster</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row" className="text-left font-normal">Actual spread (SD of the estimates)</th>
              <td className="text-right font-semibold">{ppt(srsSD)}</td>
              <td className="text-right font-semibold">{ppt(clSD)}</td>
            </tr>
            <tr>
              <th scope="row" className="text-left font-normal">Naive iid SE, average</th>
              <td className="text-right">{ppt(mean(sim.srs.naive))}</td>
              <td className="text-right">{ppt(mean(sim.cluster.naive))}</td>
            </tr>
            <tr>
              <th scope="row" className="text-left font-normal">Cluster-robust SE (by neighbourhood), average</th>
              <td className="text-right text-muted">not needed</td>
              <td className="text-right">{ppt(mean(sim.cluster.robust))}</td>
            </tr>
            <tr>
              <th scope="row" className="text-left font-normal">Design effect, Var(design) / Var(SRS)</th>
              <td className="text-right">1 (reference)</td>
              <td className="text-right font-semibold">{fmt(deff, 'num2')}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <Note>
        Both designs give every adult the same chance of selection, so the weights are equal and both estimators are the
        plain mean. The naive SE assumes {fmt(SAMPLE_N, 'int')} independent draws; the cluster sample has only {sim.m}{' '}
        independent neighbourhoods, whose residents share a neighbourhood effect. The design effect divides the cluster
        variance by the SRS variance, {ppt(sim.srsTrueSE)} squared, computed from the population. The cluster-robust SE
        ignores the finite-population correction for sampling {sim.m} of 200 neighbourhoods, so it runs slightly high when
        many are sampled.
      </Note>
      <HeldFixed>
        The population, the outcome, the sample size ({fmt(SAMPLE_N, 'int')} adults), and equal selection probabilities.
        Only how the sample is drawn changes, and with it the repeated-sampling spread.
      </HeldFixed>
    </div>
  );
}

// ------------------------------------------------------------------ stage 3

const OLS_N = 5000;

function Target({
  het,
  setHet,
  spread,
  setSpread,
  seed,
  setSeed,
}: {
  het: number;
  setHet: (v: number) => void;
  spread: number;
  setSpread: (v: number) => void;
  seed: number;
  setSeed: (f: (s: number) => number) => void;
}) {
  const scn = useMemo(() => wfhScenario(het, spread), [het, spread]);
  const est = useMemo(() => scenarioSampleOLS(scn, OLS_N, deriveSeed('sampler-stage3', seed)), [scn, seed]);
  const taus = scn.cellTau;
  const lo = Math.min(...taus, est.beta - 1.96 * est.seHC1);
  const hi = Math.max(...taus, est.beta + 1.96 * est.seHC1);
  const pad = (hi - lo) * 0.06 || 0.02;
  const maxBar = Math.max(...scn.cells.map((c) => Math.max(c.share, c.omega)));

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Slider
          label="Effect heterogeneity: how far cell effects spread around the PATE"
          min={0}
          max={2}
          step={0.1}
          value={het}
          onChange={setHet}
          display={`${fmt(het, 'num1')}× baseline`}
          hint="0 = the same effect in every cell."
        />
        <Slider
          label="Selection into treatment: how unequal treated shares are across cells"
          min={0}
          max={2}
          step={0.1}
          value={spread}
          onChange={setSpread}
          display={`${fmt(spread, 'num1')}× baseline`}
          hint="0 = every cell has the same treated share (full overlap)."
        />
      </div>
      <p className="mt-3 text-ink-2">
        Outcome: log wage. Treatment: working from home. Regression: log wage on the treatment plus dummies for the six age ×
        degree cells.
      </p>
      <div className="mt-3">
        <DotRows
          ariaLabel={`Regression target ${fmt(scn.olsTarget, 'num3')}, PATE ${fmt(scn.pate, 'num3')}, ATT ${fmt(scn.att, 'num3')}, ATU ${fmt(scn.atu, 'num3')}; one-sample OLS estimate ${fmt(est.beta, 'num3')}.`}
          domain={[lo - pad, hi + pad]}
          tickFormat={(v) => fmt(v, 'num2')}
          rows={[
            { key: 'ols', label: 'What OLS with cell controls targets, Σ ω·τ', value: scn.olsTarget, valueText: fmt(scn.olsTarget, 'num3'), shape: 'diamond', color: 'var(--role-highlight)', strong: true },
            { key: 'pate', label: 'PATE: average effect, everyone', value: scn.pate, valueText: fmt(scn.pate, 'num3'), shape: 'circle', color: 'var(--role-weighted)' },
            { key: 'att', label: 'ATT: average effect, the treated', value: scn.att, valueText: fmt(scn.att, 'num3'), shape: 'triangle', color: 'var(--role-treated)' },
            { key: 'atu', label: 'ATU: average effect, the untreated', value: scn.atu, valueText: fmt(scn.atu, 'num3'), shape: 'square', color: 'var(--role-control)' },
            {
              key: 'est',
              label: `OLS in one sample of ${fmt(OLS_N, 'int')} (95% CI)`,
              value: est.beta,
              lo: est.beta - 1.96 * est.seHC1,
              hi: est.beta + 1.96 * est.seHC1,
              valueText: fmt(est.beta, 'num3'),
              shape: 'diamond',
              hollow: true,
              color: 'var(--role-unweighted)',
            },
          ]}
        />
      </div>
      <div className="mt-2">
        <SeedControl seed={seed} onNext={() => setSeed((s) => s + 1)} note="Redraws only the one-sample check." />
      </div>

      <div className="mt-4 overflow-x-auto [contain:inline-size]">
        <table className="w-full min-w-[34rem] border-collapse text-sm tabular-nums [&_td]:border-b [&_td]:border-rule [&_td]:px-2 [&_td]:py-1 [&_th]:px-2 [&_th]:py-1">
          <caption className="mb-1 text-left text-xs text-ink-2">
            Each cell&apos;s implicit regression weight ω ∝ share × p(1 − p) beside its population share.{' '}
            <Swatch shape="square" color="var(--role-weighted)" hollow /> share <Swatch shape="square" color="var(--role-highlight)" /> ω
          </caption>
          <thead>
            <tr className="border-b border-[var(--border-strong)]">
              <th scope="col" className="text-left font-semibold">Cell</th>
              <th scope="col" className="text-right font-semibold">Share</th>
              <th scope="col" className="text-right font-semibold">Treated</th>
              <th scope="col" className="text-right font-semibold">Effect τ</th>
              <th scope="col" className="text-right font-semibold">Weight ω</th>
              <th scope="col" className="w-32 text-left font-semibold">
                <span className="sr-only">Bars</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {scn.cells.map((c) => (
              <tr key={c.label}>
                <th scope="row" className="text-left font-normal">{c.label}</th>
                <td className="text-right">{fmt(c.share, 'pct0')}</td>
                <td className="text-right">{fmt(c.p, 'pct0')}</td>
                <td className="text-right">{fmt(c.tau, 'num3')}</td>
                <td className="text-right font-semibold">{fmt(c.omega, 'pct0')}</td>
                <td aria-hidden="true">
                  <div className="h-1.5 border border-[var(--role-weighted)]" style={{ width: `${(c.share / maxBar) * 100}%` }} />
                  <div className="mt-0.5 h-1.5 bg-[var(--role-highlight)]" style={{ width: `${(c.omega / maxBar) * 100}%` }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Note>
        The coefficient averages the cell effects with weights proportional to share × p(1 − p), the variance of treatment
        within the cell. Cells where treatment is common (the college cells) get more weight than their share of the
        population; cells where almost no one is treated get little. Set either slider to 0 and the target meets the PATE.
      </Note>
      <HeldFixed>
        The population, the six cells used as controls, each resident&apos;s baseline wage, and the PATE (
        {fmt(scn.pate, 'num3')}): heterogeneity stretches the cell effects around it. Treatment is redrawn with each
        resident&apos;s own fixed random number, so the sliders change rates and effects, not people. The contrasts are
        simulated effects in a synthetic population, not estimates from data.
      </HeldFixed>
    </div>
  );
}
