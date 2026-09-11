'use client';

import { useId, useMemo, useState } from 'react';
import type { Format, ReplicatesFigure, ReplicateUnit } from '@/lib/types';
import { DotRows, HeldFixed, Note, Segmented, Swatch, WidgetFrame } from './ui';
import { fmt, isPct } from './format';

type Unit = ReplicateUnit & { naive_se?: number | null };
type View = 'rank' | 'uncertainty' | 'topk';

/** 90% margin of error, the ACS convention. */
const Z90 = 1.645;

/** SE = sqrt(scale * sum_r (theta_r - theta)^2), centred on the full-sample estimate. */
export function replicateSE(theta: number, reps: number[], scale: number): number {
  let ss = 0;
  for (const r of reps) ss += (r - theta) ** 2;
  return Math.sqrt(scale * ss);
}

function moeText(v: number, format: Format): string {
  if (isPct(format)) {
    const digits = format === 'pct0' ? 1 : format === 'pct1' ? 1 : 2;
    return `${(v * 100).toFixed(digits)} pts`;
  }
  return fmt(v, format);
}

function scaleText(scale: number, nReps: number): string {
  const num = scale * nReps;
  return Math.abs(num - Math.round(num)) < 1e-9 ? `${Math.round(num)}/${nReps}` : String(scale);
}

export function ReplicateRankingClient({ data }: { data: ReplicatesFigure }) {
  const format: Format = data.format ?? 'num2';
  const units = data.units as Unit[];
  const [view, setView] = useState<View>('rank');
  const [k, setK] = useState(Math.min(Math.max(1, data.top_k), units.length));
  const [refId, setRefId] = useState<string | null>(null);
  const kId = useId();
  const refSelectId = useId();

  const stats = useMemo(() => {
    const rows = units.map((u) => {
      const se = replicateSE(u.estimate, u.reps, data.scale);
      return { u, se, moe: Z90 * se, naiveMoe: u.naive_se != null ? Z90 * u.naive_se : null };
    });
    rows.sort((a, b) => b.u.estimate - a.u.estimate || a.u.label.localeCompare(b.u.label));
    return rows;
  }, [units, data.scale]);

  const reference = stats.find((s) => s.u.id === refId) ?? stats[0];
  const rescale = Math.sqrt(data.scale * data.n_reps);

  // Share of rescaled replicates in which each unit ranks in the top k.
  const topShare = useMemo(() => {
    const counts = new Map<string, number>(units.map((u) => [u.id, 0]));
    const vals = units.map(() => 0);
    const order = units.map((_, i) => i);
    for (let r = 0; r < data.n_reps; r++) {
      units.forEach((u, i) => (vals[i] = u.estimate + rescale * (u.reps[r] - u.estimate)));
      order.sort((a, b) => vals[b] - vals[a] || units[a].label.localeCompare(units[b].label));
      for (let t = 0; t < k; t++) counts.set(units[order[t]].id, (counts.get(units[order[t]].id) ?? 0) + 1);
    }
    return counts;
  }, [units, data.n_reps, rescale, k]);

  // Replicate SE of each unit's difference from the reference (captures covariance across units).
  const diffs = useMemo(() => {
    const out = new Map<string, { diff: number; se: number; distinct: boolean }>();
    for (const s of stats) {
      if (s.u.id === reference.u.id) continue;
      const d0 = s.u.estimate - reference.u.estimate;
      let ss = 0;
      for (let r = 0; r < data.n_reps; r++) ss += (s.u.reps[r] - reference.u.reps[r] - d0) ** 2;
      const se = Math.sqrt(data.scale * ss);
      out.set(s.u.id, { diff: d0, se, distinct: Math.abs(d0) > Z90 * se });
    }
    return out;
  }, [stats, reference, data.n_reps, data.scale]);

  const lo = Math.min(...stats.map((s) => s.u.estimate - Math.max(s.moe, s.naiveMoe ?? 0)));
  const hi = Math.max(...stats.map((s) => s.u.estimate + Math.max(s.moe, s.naiveMoe ?? 0)));
  const pad = (hi - lo) * 0.04;
  const domain: [number, number] = [lo - pad, hi + pad];
  const hasNaive = stats.some((s) => s.naiveMoe != null);
  const labelWidth = Math.min(170, 24 + 7 * Math.max(...stats.map((s) => s.u.label.length + 4)));
  const nDistinct = [...diffs.values()].filter((d) => d.distinct).length;

  return (
    <WidgetFrame title={data.title ?? 'Which differences are real?'} subtitle={data.measure_label}>
      <Segmented<View>
        legend="View"
        value={view}
        onChange={setView}
        options={[
          { value: 'rank', label: 'Rank' },
          { value: 'uncertainty', label: 'Uncertainty' },
          { value: 'topk', label: 'Top-k frequency' },
        ]}
      />

      {view === 'rank' ? (
        <div className="mt-4">
          <DotRows
            ariaLabel={`Point estimates in rank order: ${stats.map((s, i) => `${i + 1}. ${s.u.label} ${fmt(s.u.estimate, format)}`).join('; ')}`}
            domain={domain}
            tickFormat={format}
            labelWidth={labelWidth}
            valueWidth={64}
            rows={stats.map((s, i) => ({
              key: s.u.id,
              label: `${i + 1}. ${s.u.label}`,
              value: s.u.estimate,
              valueText: fmt(s.u.estimate, format),
              color: 'var(--role-weighted)',
            }))}
          />
          <Note>A league table of point estimates. It looks definitive; the other two views ask how much of the order the data support.</Note>
        </div>
      ) : null}

      {view === 'uncertainty' ? (
        <div className="mt-4">
          <div className="mb-2 flex flex-wrap items-end gap-x-4 gap-y-2">
            <div>
              <label htmlFor={refSelectId} className="block text-xs font-medium text-ink-2">
                Compare every unit with
              </label>
              <select
                id={refSelectId}
                value={reference.u.id}
                onChange={(e) => setRefId(e.target.value)}
                className="mt-1 rounded-md border border-[var(--border-strong)] bg-surface px-2 py-1 text-sm text-ink focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
              >
                {stats.map((s) => (
                  <option key={s.u.id} value={s.u.id}>
                    {s.u.label}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-xs text-ink-2">
              <Swatch color="var(--role-design)" /> filled: differs from {reference.u.label} by more than the 90% MOE of the difference ·{' '}
              <Swatch color="var(--role-design)" hollow /> hollow: cannot be told apart
              {hasNaive ? (
                <>
                  {' '}
                  · dashed line: naive MOE that ignores the design
                </>
              ) : null}
            </p>
          </div>
          <DotRows
            ariaLabel={`Estimates with 90% margins of error from ${data.n_reps} ${data.method} replicates. ${nDistinct} of ${stats.length - 1} units differ from ${reference.u.label} by more than the margin of error of the difference.`}
            domain={domain}
            tickFormat={format}
            labelWidth={labelWidth}
            valueWidth={120}
            rows={stats.map((s, i) => {
              const d = diffs.get(s.u.id);
              const isRef = s.u.id === reference.u.id;
              return {
                key: s.u.id,
                label: `${i + 1}. ${s.u.label}`,
                value: s.u.estimate,
                lo: s.u.estimate - s.moe,
                hi: s.u.estimate + s.moe,
                lo2: s.naiveMoe != null ? s.u.estimate - s.naiveMoe : undefined,
                hi2: s.naiveMoe != null ? s.u.estimate + s.naiveMoe : undefined,
                valueText: `${fmt(s.u.estimate, format)} ± ${moeText(s.moe, format)}`,
                shape: isRef ? 'diamond' : 'circle',
                strong: isRef,
                hollow: !isRef && !d?.distinct,
                color: isRef ? 'var(--role-highlight)' : 'var(--role-design)',
              };
            })}
          />
          <Note>
            SE = √({scaleText(data.scale, data.n_reps)} × Σ<sub>r</sub>(θ<sub>r</sub> − θ)²) over {data.n_reps} {data.method}{' '}
            replicates; MOE = 1.645 × SE (90%, the ACS convention). A difference is judged with the SE of the difference,
            computed from the replicate differences, not by whether two intervals overlap. {nDistinct} of {stats.length - 1}{' '}
            units differ from {reference.u.label} at this level, with no adjustment for making {stats.length - 1} comparisons.
          </Note>
        </div>
      ) : null}

      {view === 'topk' ? (
        <div className="mt-4">
          <div className="mb-3 flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor={kId} className="block text-xs font-medium text-ink-2">
                Size of the top group, k
              </label>
              <input
                id={kId}
                type="number"
                min={1}
                max={units.length}
                value={k}
                onChange={(e) => setK(Math.min(units.length, Math.max(1, Math.round(Number(e.target.value) || 1))))}
                className="mt-1 w-20 rounded-md border border-[var(--border-strong)] bg-surface px-2 py-1 text-sm tabular-nums text-ink focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
              />
            </div>
            <p className="text-xs text-ink-2">
              Share of {data.n_reps} rescaled replicates in which each unit ranks in the top {k}. Rows keep the point-estimate order.
            </p>
          </div>
          <ol className="space-y-1">
            {stats.map((s, i) => {
              const share = (topShare.get(s.u.id) ?? 0) / data.n_reps;
              const inTop = i < k;
              return (
                <li key={s.u.id} className="grid grid-cols-[minmax(7rem,11rem)_minmax(0,1fr)_4.5rem] items-center gap-2">
                  <span className={inTop ? 'font-semibold' : undefined}>
                    {i + 1}. {s.u.label}
                  </span>
                  <span className="relative h-3.5 rounded-sm bg-sunken" aria-hidden="true">
                    <span
                      className="absolute inset-y-0 left-0 rounded-sm motion-safe:transition-[width] motion-safe:duration-200"
                      style={{
                        width: `${share * 100}%`,
                        background: inTop ? 'var(--role-weighted)' : 'var(--role-unweighted)',
                      }}
                    />
                  </span>
                  <span className="text-right tabular-nums">{fmt(share, 'pct0')}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-2 text-xs text-ink-2">Bold rows (and the darker bars) are the top {k} by point estimate.</p>
          <Note tone="caveat">
            Replicates approximate the sampling spread of each estimate; they are not posterior draws. Each replicate
            deviation is rescaled by √({scaleText(data.scale, data.n_reps)} × {data.n_reps}) = {fmt(rescale, 'num2')}, so that
            one rescaled replicate θ + {fmt(rescale, 'num2')}(θ<sub>r</sub> − θ) has the variance of the estimate. The
            frequencies are a rough guide to how stable the ranking is, not probabilities that a unit truly ranks in the top{' '}
            {k}.
          </Note>
        </div>
      ) : null}

      <HeldFixed>
        The published estimates and their {data.n_reps} replicate estimates. The views change only how uncertainty is
        summarized; nothing is re-estimated.
      </HeldFixed>
    </WidgetFrame>
  );
}
