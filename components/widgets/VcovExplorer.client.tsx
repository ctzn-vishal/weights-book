'use client';

import { useMemo, useState } from 'react';
import clsx from 'clsx';
import type { CodeLang, VcovMenuFigure, VcovOption } from '@/lib/types';
import { DotRows, HeldFixed, Note, Segmented, Stat, WidgetFrame } from './ui';
import { fmt } from './format';

const LANGS: { value: CodeLang; label: string }[] = [
  { value: 'r', label: 'R · fixest' },
  { value: 'python', label: 'Python · pyfixest' },
  { value: 'stata', label: 'Stata' },
];

const VERDICT: Record<VcovOption['verdict'], { text: string; className: string }> = {
  right: { text: 'Matches the design', className: 'bg-[var(--accent-subtle)] text-[var(--accent-ink)]' },
  valid: { text: 'Valid, coarser than needed', className: 'bg-sunken text-ink-2' },
  wrong: { text: 'Misses part of the dependence', className: 'bg-sunken text-[var(--negative)]' },
  noisy: { text: 'Built for another setting', className: 'bg-sunken text-ink-2' },
};

/** Code with the changed argument emphasised; the rest stays quiet. */
function CodeLine({ code, arg }: { code: string; arg: string }) {
  const lines = code.split('\n');
  return (
    <pre className="m-0 overflow-x-auto rounded-md border border-rule bg-sunken px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed text-ink">
      {lines.map((line, i) => {
        const at = arg ? line.indexOf(arg) : -1;
        return (
          <div key={i}>
            {at === -1 ? (
              line
            ) : (
              <>
                {line.slice(0, at)}
                <mark className="rounded-sm bg-[var(--accent-subtle)] px-0.5 font-semibold text-[var(--accent-ink)]">{arg}</mark>
                {line.slice(at + arg.length)}
              </>
            )}
          </div>
        );
      })}
    </pre>
  );
}

export function VcovExplorerClient({ data }: { data: VcovMenuFigure }) {
  const [selected, setSelected] = useState(data.options.find((o) => o.verdict === 'wrong')?.key ?? data.options[0].key);
  const [lang, setLang] = useState<CodeLang>('r');
  const opt = data.options.find((o) => o.key === selected) ?? data.options[0];
  const format = data.format ?? 'num3';

  const domain = useMemo<[number, number]>(() => {
    const lo = Math.min(data.truth, ...data.options.map((o) => o.ci_low));
    const hi = Math.max(data.truth, ...data.options.map((o) => o.ci_high));
    const pad = (hi - lo) * 0.08;
    return [lo - pad, hi + pad];
  }, [data]);

  const rejects = opt.p < 0.05;
  const v = VERDICT[opt.verdict];

  return (
    <WidgetFrame title={data.title ?? 'Choose an estimator'} subtitle={data.subtitle}>
      <Segmented
        legend="Variance estimator"
        options={data.options.map((o) => ({ value: o.key, label: o.label.replace(/\s*\(.*\)$/, '') }))}
        value={opt.key}
        onChange={setSelected}
      />

      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
        <div aria-live="polite" className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <div className="text-xs text-ink-2">{opt.label}</div>
            <span className={clsx('rounded-full px-2 py-0.5 text-[0.7rem] font-medium', v.className)}>{v.text}</span>
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <div className="text-4xl font-semibold tabular-nums leading-tight text-ink">{opt.se_display}</div>
            <div className="text-sm text-ink-2">standard error</div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <Stat label="× IID" value={opt.ratio_display} />
            <Stat label="95% interval" value={<span className="text-base">{opt.ci_display}</span>} />
            <Stat
              label="p (true effect 0)"
              value={opt.p_display}
              sub={rejects ? 'rejects the truth at 5%' : 'does not reject'}
              strong={rejects}
            />
          </div>
          <p className="mt-3 text-ink-2">{opt.assumes}</p>
        </div>

        <div className="min-w-0">
          <DotRows
            ariaLabel={`Coefficient ${data.coef_display} with a 95% interval under each estimator; true value ${data.truth}. Selected: ${opt.label}, interval ${opt.ci_display}.`}
            domain={domain}
            tickFormat={format}
            reference={{ value: data.truth, label: 'True effect' }}
            rows={data.options.map((o) => ({
              key: o.key,
              label: o.label.replace(/\s*\(.*\)$/, ''),
              value: data.coef,
              lo: o.ci_low,
              hi: o.ci_high,
              valueText: o.ci_display,
              strong: o.key === opt.key,
              hollow: o.key !== opt.key,
              shape: o.key === opt.key ? 'diamond' : 'circle',
              color: o.key === opt.key ? 'var(--role-highlight)' : `var(--role-${o.role ?? 'naive'})`,
            }))}
            rowHeight={30}
          />
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-medium text-ink-2">The same call, one argument changed</div>
          <Segmented legend="Language" hideLegend options={LANGS} value={lang} onChange={setLang} />
        </div>
        <CodeLine code={opt.code[lang]} arg={opt.arg[lang]} />
      </div>

      {data.note ? <Note>{data.note}</Note> : null}
      <HeldFixed>
        The data set, the regression, and the coefficient ({data.coef_display}, on {fmt(data.n_obs, 'int')} observations in{' '}
        {data.states} states over {data.years} years, {data.treated_states} of them adopting the placebo policy). Only the
        variance estimator changes, so every difference between the panels is a difference in what the standard error
        assumes about which observations move together.
      </HeldFixed>
    </WidgetFrame>
  );
}
