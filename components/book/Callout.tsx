import type { ReactNode } from 'react';
import { PredictIcon } from './icons';

export type CalloutKind = 'predict' | 'note' | 'warning' | 'box' | 'definition' | 'draft';

/** Small kind glyphs; decorative (the label text follows). Kinds without one get a CSS swatch. */
function WarningGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M12 3.6 2.8 19.4h18.4L12 3.6Z" />
      <path d="M12 9.6v4.6M12 17.3h.01" />
    </svg>
  );
}
function DefinitionGlyph() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M4 5.5h6.5a2.5 2.5 0 0 1 2.5 2.5v11.5a2 2 0 0 0-2-2H4V5.5Z" />
      <path d="M20 5.5h-6.5A2.5 2.5 0 0 0 11 8v11.5a2 2 0 0 1 2-2h7V5.5Z" />
    </svg>
  );
}
const GLYPHS: Partial<Record<CalloutKind, () => ReactNode>> = {
  predict: () => <PredictIcon />,
  warning: WarningGlyph,
  definition: DefinitionGlyph,
};

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
        {GLYPHS[kind] ? GLYPHS[kind]() : <span className="co-swatch" aria-hidden="true" />}
        {label}
      </p>
      {heading ? <p className="co-title">{heading}</p> : null}
      <div className="co-body">{children}</div>
    </div>
  );
}
