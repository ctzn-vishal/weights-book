import type { ReactNode } from 'react';
import { PredictIcon } from './icons';

export type CalloutKind = 'predict' | 'note' | 'warning' | 'box' | 'definition' | 'draft';

const LABELS: Record<CalloutKind, string> = {
  predict: 'Predict first',
  note: 'Note',
  warning: 'Caution',
  box: 'Box',
  definition: 'Definition',
  draft: 'Draft',
};

/**
 * A labelled block. Kinds (CONTRACT §8):
 *   predict     "Predict first", before every key equation and interactive; set apart by a dashed accent frame
 *   note        an aside the argument does not depend on
 *   warning     a trap or a limit on interpretation
 *   box         a framed box: provenance, a classic replication
 *   definition  a term defined for the rest of the book (title = the term)
 *   draft       an author's note in the draft
 * The kind prints as a small label; `title`, when given and different, prints under it.
 */
export function Callout({ kind = 'note', title, children }: { kind?: CalloutKind; title?: string; children?: ReactNode }) {
  const label = LABELS[kind];
  if (!label) {
    throw new Error(`<Callout kind="${kind}">: unknown kind. Use one of ${Object.keys(LABELS).join(', ')}.`);
  }
  const heading = title && title.trim().toLowerCase() !== label.toLowerCase() ? title : null;
  return (
    <div className={`co co-${kind}`} role="note" aria-label={heading ? `${label}: ${heading}` : label}>
      <p className="co-label">
        {kind === 'predict' ? <PredictIcon /> : null}
        {label}
      </p>
      {heading ? <p className="co-title">{heading}</p> : null}
      <div className="co-body">{children}</div>
    </div>
  );
}
