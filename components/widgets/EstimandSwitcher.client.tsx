'use client';

import { useState } from 'react';
import type { EstimandSetFigure } from '@/lib/types';
import { DotRows, HeldFixed, Note, Segmented, WidgetFrame } from './ui';
import { fmt } from './format';

export function EstimandSwitcherClient({ data }: { data: EstimandSetFigure }) {
  const [selected, setSelected] = useState(data.options[0].id);
  const opt = data.options.find((o) => o.id === selected) ?? data.options[0];
  const format = data.format ?? 'num2';
  const values = data.options.map((o) => o.estimate);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = hi - lo > 1e-9 ? (hi - lo) * 0.3 : Math.max(Math.abs(hi) * 0.05, 0.01);

  return (
    <WidgetFrame title={data.title ?? data.question} subtitle={data.title ? data.question : data.subtitle}>
      <Segmented
        legend="Choose the estimand"
        options={data.options.map((o) => ({ value: o.id, label: o.label }))}
        value={opt.id}
        onChange={setSelected}
      />
      <div className="mt-4 grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div aria-live="polite">
          <div className="text-xs text-ink-2">{opt.label}</div>
          <div className="text-4xl font-semibold tabular-nums leading-tight text-ink">{opt.display}</div>
          <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1">
            <dt className="text-ink-2">Unit</dt>
            <dd>{opt.unit}</dd>
            <dt className="text-ink-2">Weight</dt>
            <dd className="font-mono text-[0.95em]">{opt.weight}</dd>
            <dt className="text-ink-2">Records (n)</dt>
            <dd className="tabular-nums">{fmt(opt.n, 'int')}</dd>
          </dl>
          {opt.note ? <p className="mt-3 text-ink-2">{opt.note}</p> : null}
        </div>
        <DotRows
          ariaLabel={`${data.question} ${data.options.map((o) => `${o.label}: ${o.display}`).join('; ')}. Selected: ${opt.label}.`}
          domain={[lo - pad, hi + pad]}
          tickFormat={format}
          rows={data.options.map((o) => ({
            key: o.id,
            label: o.label,
            value: o.estimate,
            valueText: o.display,
            strong: o.id === opt.id,
            hollow: o.id !== opt.id,
            shape: o.id === opt.id ? 'diamond' : 'circle',
            color: o.id === opt.id ? 'var(--role-highlight)' : 'var(--role-unweighted)',
          }))}
        />
      </div>
      {data.note ? <Note>{data.note}</Note> : null}
      <HeldFixed>
        The data and the indicator are the same for every option. Only the unit of analysis and the weight change, so
        each option answers a different question: these are different estimands, not competing estimates of one.
      </HeldFixed>
    </WidgetFrame>
  );
}
