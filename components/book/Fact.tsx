import { Fragment, useId, type ReactNode } from 'react';
import { formatCount } from '@/lib/format';
import { getFact } from '@/lib/registry';
import type { Fact as FactData } from '@/lib/types';

/** CONTRACT §5 variance codes, spelled out for readers. */
const VARIANCE_LABELS: [RegExp, (m: RegExpExecArray) => string][] = [
  [/^taylor$/, () => 'Taylor linearization (design-based)'],
  [/^replicate_sdr\((\d+)\)$/, (m) => `Successive-difference replication, ${m[1]} replicate weights`],
  [/^replicate_brr$/, () => 'Balanced repeated replication'],
  [/^weights_only_understated$/, () => 'Weights only: design not declared, so the standard error is understated'],
  [/^cluster_robust\((.+)\)$/, (m) => `Cluster-robust, clustered by ${m[1]}`],
  [/^wild_cluster_bootstrap\((.+)\)$/, (m) => `Wild cluster bootstrap, clustered by ${m[1]}`],
  [/^none$/, () => 'None reported'],
  [/^simulation$/, () => 'Simulation'],
];

export function varianceLabel(code: string | null | undefined): string | null {
  if (!code) return null;
  for (const [re, label] of VARIANCE_LABELS) {
    const m = re.exec(code);
    if (m) return label(m);
  }
  return code;
}

/** DOM-safe id from React's useId. */
export function usePopId(prefix: string): string {
  return `${prefix}-${useId().replace(/[^A-Za-z0-9_-]/g, '')}`;
}

/**
 * The provenance card shown on hover and focus. Phrasing content only
 * (spans), because a Fact sits inside a <p>.
 */
export function FactPopover({ fact, id }: { fact: FactData; id: string }) {
  const rows: [string, ReactNode][] = [['Estimand', fact.estimand]];
  if (fact.ci_display) rows.push(['95% CI', fact.df ? `${fact.ci_display} (t, df = ${fact.df})` : fact.ci_display]);
  if (fact.n !== null && fact.n !== undefined) rows.push(['n', formatCount(fact.n)]);
  if (fact.weight) rows.push(['Weight', fact.weight]);
  const variance = varianceLabel(fact.variance);
  if (variance) rows.push(['Variance', variance]);
  rows.push(['Source', fact.source]);
  if (fact.benchmark) rows.push(['External benchmark', fact.benchmark]);
  if (fact.note) rows.push(['Note', fact.note]);
  return (
    <span className="fact-pop" role="tooltip" id={id}>
      <span className="fact-card">
        <span className="fact-head">
          {fact.display}
          {fact.unit ? <span className="u"> {fact.unit}</span> : null}
        </span>
        <span className="fact-rows">
          {rows.map(([k, v]) => (
            <Fragment key={k}>
              <span className="fact-k">{k}</span>
              <span className="fact-v">{v}</span>
            </Fragment>
          ))}
        </span>
      </span>
    </span>
  );
}

export interface FactProps {
  /** Global fact id, "<key>.<fact_key>". Unknown ids fail the build. */
  id: string;
  /** Append " (95% CI <ci_display>)". The fact must carry ci_display. */
  ci?: boolean;
  /** Print the number without the provenance popover. */
  plain?: boolean;
}

/**
 * An inline number from the artifacts. Prints `display` exactly as Python
 * formatted it; hover or keyboard focus shows estimand, n, weight, variance,
 * source, and benchmark.
 */
export function Fact({ id, ci = false, plain = false }: FactProps) {
  const fact = getFact(id);
  const popId = usePopId('fact');
  if (ci && !fact.ci_display) {
    throw new Error(`<Fact id="${id}" ci>: the fact has no ci_display, so there is no interval to print. Drop \`ci\` or export the interval.`);
  }
  const interval = ci ? ` (95% CI ${fact.ci_display})` : null;
  if (plain) {
    return (
      <span className="fact is-plain" data-fact={id}>
        <span className="fact-num">{fact.display}</span>
        {interval}
      </span>
    );
  }
  return (
    <span className="fact" data-fact={id}>
      <span className="fact-num" tabIndex={0} aria-describedby={popId}>
        {fact.display}
      </span>
      {interval}
      <FactPopover fact={fact} id={popId} />
    </span>
  );
}
