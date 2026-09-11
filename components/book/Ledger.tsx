import { getFact, getLedger } from '@/lib/registry';
import type { Ledger as LedgerData } from '@/lib/types';
import { Fact, usePopId } from './Fact';

/** The eight v3 §2.1 fields, in order. `grp` starts a new block: target, contribution, uncertainty, assumptions. */
const FIELDS: { key: keyof LedgerData; label: string; grp?: boolean }[] = [
  { key: 'target_population', label: 'Target population' },
  { key: 'estimand', label: 'Estimand' },
  { key: 'estimator', label: 'Estimator', grp: true },
  { key: 'explicit_weights', label: 'Explicit weights' },
  { key: 'implicit_weights', label: 'Implicit weights' },
  { key: 'randomness', label: 'Source of randomness', grp: true },
  { key: 'variance_estimator', label: 'Variance estimator' },
  { key: 'assumptions', label: 'Assumptions', grp: true },
];

/**
 * The Analysis Ledger for one headline result, read from ledger.json so it
 * cannot drift from the numbers. The ledger's facts print as chips, each
 * with the Fact provenance popover.
 */
export function Ledger({ id }: { id: string }) {
  const ledger = getLedger(id);
  const titleId = usePopId('ledger');
  const facts = (ledger.facts ?? []).map((fid) => ({ fid, fact: getFact(fid) }));
  return (
    <section className="ledger" aria-labelledby={titleId}>
      <div className="ledger-head">
        <span className="ledger-eyebrow">Analysis Ledger</span>
        <h3 className="ledger-title" id={titleId}>
          {ledger.title}
        </h3>
      </div>
      <dl className="ledger-grid">
        {FIELDS.map(({ key, label, grp }) => (
          <div key={key} className={grp ? 'ledger-row grp' : 'ledger-row'}>
            <dt>{label}</dt>
            <dd>{(ledger[key] as string | undefined) || '—'}</dd>
          </div>
        ))}
        {facts.length ? (
          <div className="ledger-row grp">
            <dt>Numbers reported</dt>
            <dd>
              <ul className="ledger-facts">
                {facts.map(({ fid, fact }) => (
                  <li key={fid} className="ledger-chip">
                    <Fact id={fid} />
                    {fact.unit ? <span className="u">{fact.unit}</span> : null}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
