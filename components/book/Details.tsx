import type { ReactNode } from 'react';

/** A collapsed block for derivations and asides: <Details summary="Derivation">…</Details>. */
export function Details({ summary, children }: { summary: string; children?: ReactNode }) {
  return (
    <details className="bk-details">
      <summary>{summary}</summary>
      <div className="bk-details-body">{children}</div>
    </details>
  );
}
