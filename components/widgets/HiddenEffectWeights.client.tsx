'use client';

import { useMemo, useState } from 'react';
import type { CellsFigure, Format } from '@/lib/types';
import { angristWeights, deriveSeed, makeNormal, mulberry32, olsCells, twoGroupPlim } from '@/lib/synthpop';
import { DotRows, HeldFixed, Note, SeedControl, Slider, Swatch, WidgetFrame, buttonClass, type DotRowDatum } from './ui';
import { fmt, signed } from './format';

interface Params {
  pi: number;
  p1: number;
  p0: number;
  tau1: number;
  tau0: number;
}
const DEFAULTS: Params = { pi: 0.35, p1: 0.3, p0: 0.06, tau1: 0.2, tau0: 0.04 };
const SIM_N = 5000;

/** One simulated sample from the two-group model: OLS of y on the treatment and a group dummy. */
function simulate(a: Params, seed: number) {
  const rng = mulberry32(deriveSeed('hidden-effect-weights', seed));
  const norm = makeNormal(rng);
  const y = new Float64Array(SIM_N);
  const d = new Uint8Array(SIM_N);
  const cell = new Uint8Array(SIM_N);
  for (let i = 0; i < SIM_N; i++) {
    const g = rng() < a.pi ? 1 : 0;
    cell[i] = g;
    d[i] = rng() < (g ? a.p1 : a.p0) ? 1 : 0;
    y[i] = 0.3 * g + (g ? a.tau1 : a.tau0) * d[i] + 0.4 * norm();
  }
  return olsCells(y, d, cell, 2);
}

function Bars({ share, weight, label }: { share: number; weight: number; label: string }) {
  return (
    <div className="grid grid-cols-[5.5rem_minmax(0,1fr)_3.5rem] items-center gap-x-2 gap-y-1">
      <span className="row-span-2 font-medium">{label}</span>
      <span className="relative h-3 rounded-sm border border-[var(--role-weighted)]" aria-hidden="true">
        <span className="absolute inset-y-0 left-0 bg-[var(--chart-band)]" style={{ width: `${share * 100}%` }} />
        <span className="absolute inset-y-0 border-r-2 border-[var(--role-weighted)]" style={{ width: `${share * 100}%` }} />
      </span>
      <span className="text-right tabular-nums">{fmt(share, 'pct0')}</span>
      <span className="relative h-3 rounded-sm bg-sunken" aria-hidden="true">
        <span className="absolute inset-y-0 left-0 rounded-sm bg-[var(--role-highlight)]" style={{ width: `${weight * 100}%` }} />
      </span>
      <span className="text-right font-semibold tabular-nums">{fmt(weight, 'pct0')}</span>
    </div>
  );
}

function averageRows(v: { regression: number; pate: number; att: number; atu: number }, f: Format): DotRowDatum[] {
  return [
    { key: 'ols', label: 'Regression (implicit weights)', value: v.regression, valueText: fmt(v.regression, f), shape: 'diamond', color: 'var(--role-highlight)', strong: true },
    { key: 'pate', label: 'Population-weighted (PATE)', value: v.pate, valueText: fmt(v.pate, f), shape: 'circle', color: 'var(--role-weighted)' },
    { key: 'att', label: 'Treated-weighted (ATT)', value: v.att, valueText: fmt(v.att, f), shape: 'triangle', color: 'var(--role-treated)' },
    { key: 'atu', label: 'Untreated-weighted (ATU)', value: v.atu, valueText: fmt(v.atu, f), shape: 'square', color: 'var(--role-control)' },
  ];
}

function domainOf(values: number[]): [number, number] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = hi - lo > 1e-9 ? (hi - lo) * 0.15 : 0.02;
  return [lo - pad, hi + pad];
}

export function HiddenEffectWeightsClient({ cells }: { cells?: CellsFigure }) {
  const [a, setA] = useState<Params>(DEFAULTS);
  const [seed, setSeed] = useState(1);
  const set = (k: keyof Params) => (v: number) => setA((prev) => ({ ...prev, [k]: v }));
  const r = useMemo(() => twoGroupPlim(a), [a]);
  const sim = useMemo(() => simulate(a, seed), [a, seed]);
  const v1 = a.p1 * (1 - a.p1);
  const v0 = a.p0 * (1 - a.p0);

  return (
    <WidgetFrame
      title="The variance-weighting machine"
      subtitle="Two groups, a binary treatment, and a regression with a group dummy. Which average of the two group effects does the regression coefficient estimate?"
    >
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <Slider label="Share of the population in group 1 (s)" min={0.05} max={0.95} step={0.01} value={a.pi} onChange={set('pi')} display={fmt(a.pi, 'pct0')} />
        <div className="hidden sm:block" />
        <Slider label="Treated share in group 1 (p₁)" min={0.01} max={0.99} step={0.01} value={a.p1} onChange={set('p1')} display={fmt(a.p1, 'pct0')} />
        <Slider label="Treated share in group 0 (p₀)" min={0.01} max={0.99} step={0.01} value={a.p0} onChange={set('p0')} display={fmt(a.p0, 'pct0')} />
        <Slider label="Effect in group 1 (τ₁)" min={-0.2} max={0.4} step={0.01} value={a.tau1} onChange={set('tau1')} display={fmt(a.tau1, 'num2')} />
        <Slider label="Effect in group 0 (τ₀)" min={-0.2} max={0.4} step={0.01} value={a.tau0} onChange={set('tau0')} display={fmt(a.tau0, 'num2')} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={buttonClass} onClick={() => setA((p) => ({ ...p, tau0: p.tau1 }))}>
          Knife edge: equal effects
        </button>
        <button type="button" className={buttonClass} onClick={() => setA((p) => ({ ...p, p0: p.p1 }))}>
          Knife edge: equal treatment variance
        </button>
        <button type="button" className={buttonClass} onClick={() => setA(DEFAULTS)}>
          Reset
        </button>
      </div>

      <div className="mt-5 grid gap-6 md:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div>
          <DotRows
            ariaLabel={`Regression coefficient ${fmt(r.ols, 'num3')}, PATE ${fmt(r.pate, 'num3')}, ATT ${fmt(r.att, 'num3')}, ATU ${fmt(r.atu, 'num3')}.`}
            domain={domainOf([r.ols, r.pate, r.att, r.atu, a.tau1, a.tau0])}
            tickFormat={(x) => fmt(x, 'num2')}
            rows={averageRows(r, 'num3')}
          />
          <p className="mt-2 text-xs leading-relaxed text-ink-2">
            plim β̂ = [s·p₁(1−p₁)·τ₁ + (1−s)·p₀(1−p₀)·τ₀] / [s·p₁(1−p₁) + (1−s)·p₀(1−p₀)] = [{fmt(a.pi * v1, 'num3')} × {fmt(a.tau1, 'num2')} +{' '}
            {fmt((1 - a.pi) * v0, 'num3')} × {fmt(a.tau0, 'num2')}] / {fmt(a.pi * v1 + (1 - a.pi) * v0, 'num3')} = {fmt(r.ols, 'num3')}
          </p>
        </div>
        <div>
          <div className="mb-2 text-xs text-ink-2">
            <Swatch shape="square" color="var(--role-weighted)" hollow /> population share ·{' '}
            <Swatch shape="square" color="var(--role-highlight)" /> implicit regression weight ω
          </div>
          <div className="space-y-3">
            <Bars label="Group 1" share={a.pi} weight={r.weight1} />
            <Bars label="Group 0" share={1 - a.pi} weight={1 - r.weight1} />
          </div>
          <ul className="mt-3 space-y-1 text-xs leading-relaxed">
            <li>
              <span className="font-semibold">Equal effects? </span>
              {r.equalEffects ? (
                <span className="font-semibold text-ink">Yes: a knife edge. Every weighting gives the same number.</span>
              ) : (
                <span className="text-ink-2">No, τ₁ − τ₀ = {signed(a.tau1 - a.tau0, 2)}.</span>
              )}
            </li>
            <li>
              <span className="font-semibold">Equal treatment variance? </span>
              {r.equalVariance ? (
                <span className="font-semibold text-ink">Yes: a knife edge. The implicit weights equal the population shares, so the regression hits the PATE.</span>
              ) : (
                <span className="text-ink-2">
                  No, p₁(1−p₁) = {fmt(v1, 'num3')} and p₀(1−p₀) = {fmt(v0, 'num3')}.
                </span>
              )}
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-4 rounded-md border border-rule bg-sunken px-3 py-2">
        <SeedControl
          seed={seed}
          onNext={() => setSeed((s) => s + 1)}
          note={`One simulated sample of ${fmt(SIM_N, 'int')} from these settings.`}
        />
        <p className="mt-1 tabular-nums" aria-live="polite">
          OLS coefficient in the sample: <span className="font-semibold">{fmt(sim.beta, 'num3')}</span> (robust SE{' '}
          {fmt(sim.seHC1, 'num3')}), against a probability limit of {fmt(r.ols, 'num3')} and a PATE of {fmt(r.pate, 'num3')}.
        </p>
      </div>

      <HeldFixed>
        Two groups; a binary treatment with a constant effect inside each group; a regression of the outcome on the
        treatment and a group dummy, with no other controls. The averages are population quantities; only the one-sample
        check involves sampling.
      </HeldFixed>

      {cells ? <CellsPanel data={cells} /> : null}
    </WidgetFrame>
  );
}

type SortKey = 'label' | 'pop_share' | 'treat_share' | 'effect' | 'omega' | 'ratio';

function CellsPanel({ data }: { data: CellsFigure }) {
  const f: Format = data.effect_format ?? 'num3';
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'omega', desc: true });
  const avg = useMemo(
    () => angristWeights(data.cells.map((c) => ({ share: c.pop_share, p: c.treat_share, tau: c.effect }))),
    [data.cells],
  );
  const shareTotal = data.cells.reduce((s, c) => s + c.pop_share, 0);
  const rows = data.cells.map((c, i) => {
    const share = c.pop_share / shareTotal;
    return { ...c, share, omega: avg.omega[i], ratio: share > 0 ? avg.omega[i] / share : NaN };
  });
  const val = (r: (typeof rows)[number], k: SortKey) => (k === 'label' ? r.label : k === 'pop_share' ? r.share : r[k]);
  rows.sort((x, y) => {
    const a = val(x, sort.key);
    const b = val(y, sort.key);
    const c = typeof a === 'string' ? a.localeCompare(b as string) : (a as number) - (b as number);
    return sort.desc ? -c : c;
  });
  const maxBar = Math.max(...rows.map((r) => Math.max(r.share, r.omega)));
  const head = (key: SortKey, label: string, align: 'left' | 'right' = 'right') => (
    <th
      scope="col"
      aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}
      className={align === 'right' ? 'text-right' : 'text-left'}
    >
      <button
        type="button"
        onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== 'label' }))}
        className="font-semibold text-ink hover:underline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
      >
        {label}
        <span aria-hidden="true" className="ml-0.5 text-muted">
          {sort.key === key ? (sort.desc ? '▼' : '▲') : '↕'}
        </span>
      </button>
    </th>
  );
  const coefRows: DotRowDatum[] = [...averageRows(avg, f)];
  if (data.wls_coef != null) coefRows.push({ key: 'wls', label: 'Fitted survey-weighted coefficient', value: data.wls_coef, valueText: fmt(data.wls_coef, f), shape: 'diamond', color: 'var(--role-highlight)', hollow: true });
  if (data.ols_coef != null) coefRows.push({ key: 'olsfit', label: 'Fitted unweighted coefficient', value: data.ols_coef, valueText: fmt(data.ols_coef, f), shape: 'diamond', color: 'var(--role-unweighted)', hollow: true });

  return (
    <div className="mt-6 border-t border-rule pt-4">
      <div className="text-base font-semibold">{data.title ?? 'The real cells'}</div>
      <p className="mt-1 text-ink-2">
        {data.subtitle ?? `${data.outcome_label}: ${data.treatment_label.toLowerCase()} versus not, cell by cell.`} Implicit
        weight ω ∝ population share × p(1 − p), the weight each cell&apos;s effect gets in a survey-weighted regression with a
        full set of cell dummies.
      </p>
      <div className="mt-3 overflow-x-auto [contain:inline-size]">
        <table className="w-full min-w-[40rem] border-collapse text-sm tabular-nums [&_td]:border-b [&_td]:border-rule [&_td]:px-2 [&_td]:py-1 [&_th]:border-b [&_th]:border-[var(--border-strong)] [&_th]:px-2 [&_th]:py-1">
          <caption className="sr-only">Cells sorted by {sort.key}; click a column header to sort.</caption>
          <thead>
            <tr>
              {head('label', 'Cell', 'left')}
              {head('pop_share', 'Pop. share')}
              {head('treat_share', `${data.treatment_label} share`)}
              {head('effect', 'Effect')}
              {head('omega', 'Implicit weight ω')}
              {head('ratio', 'ω ÷ share')}
              <th scope="col" className="text-left font-semibold">
                <span className="sr-only">Bars: </span>
                <Swatch shape="square" color="var(--role-weighted)" hollow /> share <Swatch shape="square" color="var(--role-highlight)" /> ω
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.label}>
                <td className="text-left">{c.label}</td>
                <td className="text-right">{fmt(c.share, 'pct1')}</td>
                <td className="text-right">{fmt(c.treat_share, 'pct0')}</td>
                <td className="text-right">
                  {fmt(c.effect, f)}
                  {c.effect_se != null ? <span className="text-muted"> ± {fmt(1.96 * c.effect_se, f)}</span> : null}
                </td>
                <td className="text-right font-semibold">{fmt(c.omega, 'pct1')}</td>
                <td className="text-right">{fmt(c.ratio, 'ratio2')}</td>
                <td className="w-32" aria-hidden="true">
                  <div className="relative h-1.5 border border-[var(--role-weighted)]" style={{ width: `${(c.share / maxBar) * 100}%` }} />
                  <div className="mt-0.5 h-1.5 bg-[var(--role-highlight)]" style={{ width: `${(c.omega / maxBar) * 100}%` }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs text-muted">Effect intervals are ±1.96 SE where an SE is supplied.</p>
      <div className="mt-4">
        <DotRows
          ariaLabel={`Implied averages of the cell effects: regression-weighted ${fmt(avg.regression, f)}, population-weighted ${fmt(avg.pate, f)}, treated-weighted ${fmt(avg.att, f)}, untreated-weighted ${fmt(avg.atu, f)}.`}
          domain={domainOf(coefRows.map((r) => r.value))}
          tickFormat={f}
          rows={coefRows}
        />
      </div>
      <Note tone="caveat">
        These contrasts are descriptive. Each cell effect is an adjusted difference in {data.outcome_label.toLowerCase()} between
        people who did and did not {data.treatment_label.toLowerCase().startsWith('tele') ? 'telework' : 'receive the treatment'} in
        that cell, not a causal effect; the four averages differ only in how they weight the same cell contrasts.
      </Note>
    </div>
  );
}
