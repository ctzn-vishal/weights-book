'use client';

/**
 * Chapter 2: build a survey weight in stages on the synthetic population.
 * An oversampled sample (G selected at 4 times the rate of everyone else) loses
 * respondents to nonresponse that depends on age and degree. Stages: unweighted
 * -> design weights -> nonresponse adjustment -> raking -> trimming -> re-raking.
 */

import { useMemo, useState } from 'react';
import { scaleLinear } from 'd3-scale';
import {
  N_POP,
  deriveSeed,
  getPopulation,
  nonresponse,
  oversample,
  seFrequency,
  seLinearized,
  sePrecision,
  weightPipeline,
  type StageKey,
  type StageResult,
} from '@/lib/synthpop';
import { HeldFixed, Histogram, Note, SeedControl, Segmented, Slider, WidgetFrame, binValues, buttonClass, useMeasuredWidth } from './ui';
import { fmt, pts } from './format';

const N_SAMPLE = 2000;
const FACTOR = 4;
const MC_REPS = 100;

const STAGES: Record<StageKey, { label: string; short: string; what: string }> = {
  unweighted: { label: 'Unweighted', short: 'Raw', what: 'Every respondent counts once.' },
  design: { label: 'Design weights', short: 'Design', what: 'd = 1/π undoes the oversampling of G.' },
  nonresponse: { label: 'Nonresponse-adjusted', short: 'Nonresp.', what: 'Within each age × degree cell, respondents also carry the design weight of that cell’s nonrespondents.' },
  raked: { label: 'Raked', short: 'Raked', what: 'Scaled in turns until the weighted totals match the known age × degree and G totals.' },
  trimmed: { label: 'Trimmed', short: 'Trimmed', what: 'Weights above the cap are cut and the excess spread over the others.' },
  final: { label: 'Final (re-raked)', short: 'Final', what: 'Raked again so the margins hold after trimming.' },
};
const ORDER: StageKey[] = ['unweighted', 'design', 'nonresponse', 'raked', 'trimmed', 'final'];
const ppt = (v: number, d = 2) => `${(v * 100).toFixed(d)} pts`;
const sci = (v: number) => (v === 0 ? '0' : v.toExponential(1).replace('e-', '×10⁻').replace(/⁻(\d+)/, (_, d: string) => '⁻' + [...d].map((c) => '⁰¹²³⁴⁵⁶⁷⁸⁹'[Number(c)]).join('')));

function Waterfall({ stages, truth, selected }: { stages: StageResult[]; truth: number; selected: StageKey }) {
  const [ref, width] = useMeasuredWidth(600);
  const h = 230;
  const m = { l: 42, r: 12, t: 22, b: 30 };
  const est = stages.map((s) => s.estimate);
  const y = scaleLinear()
    .domain([Math.min(0.08, ...est, truth) - 0.004, Math.max(0.17, ...est, truth) + 0.004])
    .range([h - m.b, m.t])
    .nice();
  const band = (width - m.l - m.r) / stages.length;
  const cx = (i: number) => m.l + band * (i + 0.5);
  const bw = Math.min(44, band * 0.55);
  return (
    <div ref={ref} className="w-full [contain:inline-size]">
      <svg
        viewBox={`0 0 ${width} ${h}`}
        width="100%"
        role="img"
        className="block h-auto overflow-visible"
        aria-label={`Estimated uninsured rate by weighting stage: ${stages.map((s) => `${STAGES[s.key].label} ${fmt(s.estimate, 'pct1')}`).join('; ')}. Simulated population truth ${fmt(truth, 'pct1')}.`}
      >
        {y.ticks(5).map((t) => (
          <g key={t}>
            <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" />
            <text x={m.l - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--chart-tick)">
              {fmt(t, 'pct0')}
            </text>
          </g>
        ))}
        <line x1={m.l} x2={width - m.r} y1={y(truth)} y2={y(truth)} stroke="var(--role-truth)" strokeWidth={1.5} strokeDasharray="5 3" />
        <text x={width - m.r} y={y(truth) - 5} textAnchor="end" fontSize={11} fontWeight={600} fill="var(--role-truth)">
          Simulated truth {fmt(truth, 'pct1')}
        </text>
        {stages.map((s, i) => {
          const prev = i === 0 ? s.estimate : stages[i - 1].estimate;
          const top = Math.min(y(prev), y(s.estimate));
          const hgt = Math.max(1.5, Math.abs(y(prev) - y(s.estimate)));
          const d = s.estimate - prev;
          const isSel = s.key === selected;
          return (
            <g key={s.key}>
              {i > 0 ? (
                <line x1={cx(i - 1) + bw / 2} x2={cx(i) - bw / 2} y1={y(prev)} y2={y(prev)} stroke="var(--chart-label)" strokeDasharray="2 2" />
              ) : null}
              <rect x={cx(i) - bw / 2} y={top} width={bw} height={hgt} fill="var(--role-weighted)" fillOpacity={0.22} stroke="var(--role-weighted)" strokeWidth={1} />
              <line x1={cx(i) - bw / 2} x2={cx(i) + bw / 2} y1={y(s.estimate)} y2={y(s.estimate)} stroke="var(--role-weighted)" strokeWidth={3} />
              <text x={cx(i)} y={top - 5} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--chart-annotation)">
                {fmt(s.estimate, 'pct1')}
              </text>
              {i > 0 && Math.abs(d) >= 0.0005 ? (
                <text x={cx(i)} y={top + hgt + 12} textAnchor="middle" fontSize={10} fill="var(--chart-label)">
                  {d > 0 ? '▲' : '▼'} {pts(d)}
                </text>
              ) : null}
              <text x={cx(i)} y={h - m.b + 17} textAnchor="middle" fontSize={11} fontWeight={isSel ? 700 : 400} fill="var(--chart-annotation)">
                {STAGES[s.key].short}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function WeightBuilder() {
  const pop = getPopulation();
  const truth = pop.truths.prevalence;
  const [seed, setSeed] = useState(1);
  const [cap, setCap] = useState(2);
  const [histStage, setHistStage] = useState<StageKey>('final');
  const [mc, setMc] = useState<{ cap: number; sd: number; mean: number } | null>(null);

  const sample = useMemo(() => nonresponse(oversample(N_SAMPLE, FACTOR, seed), seed), [seed]);
  const p = useMemo(() => weightPipeline(sample, cap), [sample, cap]);
  const nResp = p.resp.length;
  const finalStage = p.stages[p.stages.length - 1];
  const w = finalStage.weights;
  const shown = p.stages.find((s) => s.key === histStage)!;
  const rel = useMemo(() => {
    const mean = shown.total / shown.weights.length;
    return Array.from(shown.weights, (x) => x / mean);
  }, [shown]);
  const three = [
    { key: 'f', name: 'Frequency weights fᵢ', se: seFrequency(p.y, w), why: `Each record stands for fᵢ identical records, so the software sees Σfᵢ = ${fmt(Math.round(finalStage.total), 'int')} observations and reports a far smaller SE.` },
    { key: 'a', name: 'Precision weights aᵢ', se: sePrecision(p.y, w), why: 'Each outcome is treated as an average with variance σ²/aᵢ; the weights are read as known precision, so the variance that unequal weights add is ignored.' },
    { key: 'w', name: 'Sampling weights wᵢ', se: seLinearized(p.y, w), why: 'Each record represents wᵢ people; this weights-only linearized SE counts the weight dispersion but treats the weights as fixed and ignores the strata and the raking.' },
  ];

  const runMc = () => {
    const est: number[] = [];
    for (let r = 0; r < MC_REPS; r++) {
      const sd = deriveSeed('weight-builder-mc', r);
      const pr = weightPipeline(nonresponse(oversample(N_SAMPLE, FACTOR, sd), sd), cap);
      est.push(pr.stages[pr.stages.length - 1].estimate);
    }
    const mean = est.reduce((a, b) => a + b, 0) / MC_REPS;
    const sd = Math.sqrt(est.reduce((a, b) => a + (b - mean) ** 2, 0) / (MC_REPS - 1));
    setMc({ cap, sd, mean });
  };

  return (
    <WidgetFrame
      title="Building a survey weight, one stage at a time"
      subtitle={`${fmt(N_SAMPLE, 'int')} adults sampled from the synthetic population, with group G selected at ${FACTOR} times the rate of everyone else; younger adults and those without a degree respond less often. Outcome: the share uninsured.`}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <SeedControl seed={seed} onNext={() => setSeed((s) => s + 1)} note={`${fmt(nResp, 'int')} of ${fmt(N_SAMPLE, 'int')} responded (${fmt(nResp / N_SAMPLE, 'pct0')})`} />
        <Slider
          label="Trimming cap, as a multiple of the mean weight"
          min={1.2}
          max={3.5}
          step={0.1}
          value={cap}
          onChange={setCap}
          display={`${fmt(cap, 'num1')}×`}
          hint={`${fmt(p.trim.trimmed, 'int')} weights capped at ${fmt(p.trim.cap, 'num1')} people each.`}
        />
      </div>

      <div className="mt-4">
        <Waterfall stages={p.stages} truth={truth} selected={histStage} />
      </div>

      <div className="mt-3 overflow-x-auto [contain:inline-size]">
        <table className="w-full min-w-[36rem] border-collapse text-sm tabular-nums [&_td]:border-b [&_td]:border-rule [&_td]:px-2 [&_td]:py-1 [&_th]:px-2 [&_th]:py-1">
          <thead>
            <tr className="border-b border-[var(--border-strong)]">
              <th scope="col" className="text-left font-semibold">Stage</th>
              <th scope="col" className="text-right font-semibold">Estimate</th>
              <th scope="col" className="text-right font-semibold">Change</th>
              <th scope="col" className="text-right font-semibold">SE, weights only</th>
              <th scope="col" className="text-right font-semibold">CV(w)</th>
              <th scope="col" className="text-right font-semibold">n<sub>Kish</sub></th>
              <th scope="col" className="text-right font-semibold">Largest ÷ mean</th>
            </tr>
          </thead>
          <tbody>
            {p.stages.map((s, i) => (
              <tr key={s.key}>
                <th scope="row" className="text-left font-normal">
                  <span className="font-medium">{STAGES[s.key].label}</span>
                  <span className="block text-xs text-ink-2">{STAGES[s.key].what}</span>
                </th>
                <td className="text-right font-semibold">{fmt(s.estimate, 'pct1')}</td>
                <td className="text-right">{i === 0 ? '–' : pts(s.estimate - p.stages[i - 1].estimate)}</td>
                <td className="text-right">{ppt(s.se)}</td>
                <td className="text-right">{fmt(s.cv, 'num2')}</td>
                <td className="text-right">{fmt(s.kishN, 'int')}</td>
                <td className="text-right">{fmt(s.maxRatio, 'ratio2')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-ink-2">
        Raking converged in {p.rake.iterations} iterations (largest margin error by iteration:{' '}
        {p.rake.history.slice(0, 6).map((h) => sci(h.maxError)).join(', ')}
        {p.rake.history.length > 6 ? ', …' : ''}). Trimming moved the margins by up to {fmt(p.trimMarginError, 'pct2')};
        re-raking {p.reRake.iterations > 0 ? `restored them in ${p.reRake.iterations} iterations` : 'had nothing to restore'}.
        Population total after raking: {fmt(N_POP, 'int')}.
      </p>

      <div className="mt-5">
        <Segmented<StageKey>
          legend="Weight distribution at stage"
          value={histStage}
          onChange={setHistStage}
          options={ORDER.map((k) => ({ value: k, label: STAGES[k].short }))}
        />
        <div className="mt-2">
          <Histogram
            bins={binValues(rel, [0, 4], 40)}
            tickFormat={(v) => `${fmt(v, 'num1')}×`}
            markers={
              histStage === 'trimmed' || histStage === 'final' || histStage === 'raked'
                ? [{ value: Math.min(4, cap), label: `Cap ${fmt(cap, 'num1')}×`, dash: '3 2', color: 'var(--role-design)' }]
                : []
            }
            color="var(--role-weighted)"
            ariaLabel={`Histogram of weights divided by their mean at the ${STAGES[histStage].label} stage; CV ${fmt(shown.cv, 'num2')}, Kish effective sample size ${fmt(shown.kishN, 'int')} of ${fmt(nResp, 'int')}.`}
          />
          <p className="text-xs text-ink-2">
            Weight ÷ mean weight. CV(w) = {fmt(shown.cv, 'num2')}; n<sub>Kish</sub> = n/(1 + CV²) = {fmt(shown.kishN, 'int')} of{' '}
            {fmt(nResp, 'int')} respondents.
          </p>
        </div>
      </div>

      <div className="mt-6 border-t border-rule pt-4">
        <div className="text-base font-semibold">Three interpretations of the same final weights</div>
        <p className="mt-1 text-ink-2">
          Every reading gives the same mean, {fmt(finalStage.estimate, 'pct1')}. The standard errors differ because each
          reading implies a different repetition.
        </p>
        <ul className="mt-3 space-y-2">
          {three.map((t) => (
            <li key={t.key} className="grid gap-x-3 sm:grid-cols-[11rem_6rem_minmax(0,1fr)]">
              <span className="font-medium">{t.name}</span>
              <span className="font-semibold tabular-nums">SE {ppt(t.se)}</span>
              <span className="text-ink-2">{t.why}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" className={buttonClass} onClick={runMc}>
            Check against {MC_REPS} repeated samples
          </button>
          {mc && mc.cap === cap ? (
            <span aria-live="polite">
              Repeated-sampling SD of the final estimate: <span className="font-semibold tabular-nums">{ppt(mc.sd)}</span>{' '}
              (mean {fmt(mc.mean, 'pct1')}).
            </span>
          ) : null}
        </div>
        <Note>
          The repeated-sampling SD reruns the whole pipeline (sampling, nonresponse, raking, trimming) on fresh samples. Only
          the sampling-weight reading aims at that repetition, and even it treats the weights as fixed: the design and the
          weight construction together determine the variance.
        </Note>
      </div>

      <HeldFixed>
        The population, the sample design ({fmt(N_SAMPLE, 'int')} adults, G oversampled {FACTOR}×), the response model (age
        and degree), and the outcome. The stages change only the weights; the respondents stay the same. The truth is the
        simulated population value, not a benchmark.
      </HeldFixed>
    </WidgetFrame>
  );
}
