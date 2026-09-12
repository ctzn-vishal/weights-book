import type { ReactNode } from 'react';

/** A collapsed block for derivations and asides: <Details summary="Derivation">…</Details>. */
export function Details({ summary, children }: { summary: string; children?: ReactNode }) {
  return (
    <details className="bk-details">
      <summary>
        <svg className="bk-details-chev" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
          <path d="M6 3.5 10.5 8 6 12.5" />
        </svg>
        <span className="bk-details-summary">{summary}</span>
      </summary>
      <div className="bk-details-body">{children}</div>
    </details>
  );
}
