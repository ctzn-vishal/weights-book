import { getFact, getLedger } from '@/lib/registry';
import type { Ledger as LedgerData, LedgerIdentification } from '@/lib/types';
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

/** Identification rows (Chapter 9), printed between the target and the estimator when a ledger carries them. */
const ID_FIELDS: { key: keyof LedgerIdentification; label: string }[] = [
  { key: 'claim_type', label: 'Claim type' },
  { key: 'observed', label: 'What is observed' },
  { key: 'assumption', label: 'Identifying assumption' },
  { key: 'made_true_by', label: 'Made credible by' },
  { key: 'without_assumption', label: 'Without the assumption' },
  { key: 'sensitivity', label: 'Sensitivity' },
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
  const idRows = ID_FIELDS.filter(({ key }) => ledger.identification?.[key]);
  return (
    <section className="ledger" aria-labelledby={titleId}>
      <div className="ledger-head">
        <span className="ledger-eyebrow">Analysis Ledger</span>
        <h3 className="ledger-title" id={titleId}>
          {ledger.title}
        </h3>
      </div>
      <dl className="ledger-grid">
        {FIELDS.flatMap(({ key, label, grp }) => {
          const row = (
            <div key={key} className={grp ? 'ledger-row grp' : 'ledger-row'}>
              <dt>{label}</dt>
              <dd>{(ledger[key] as string | undefined) || '—'}</dd>
            </div>
          );
          if (key !== 'estimand' || !idRows.length) return [row];
          return [
            row,
            ...idRows.map(({ key: k, label: l }, i) => (
              <div key={`id-${k}`} className={i === 0 ? 'ledger-row grp' : 'ledger-row'}>
                <dt>{l}</dt>
                <dd>{ledger.identification?.[k]}</dd>
              </div>
            )),
          ];
        })}
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
