import type { ReactNode } from 'react';

/**
 * The closing panels every empirical chapter ends with (v3 §3.8):
 *   <Closing><Learned>…</Learned><Changed>…</Changed><NotEstablished>…</NotEstablished></Closing>
 * The third, the limits of the analysis, is set heavier on purpose.
 */
export function Closing({ children }: { children?: ReactNode }) {
  return (
    <section className="closing" aria-label="Chapter closing">
      {children}
    </section>
  );
}

function Panel({ label, className, children }: { label: string; className: string; children?: ReactNode }) {
  return (
    <div className={`closing-panel ${className}`}>
      <h3 className="closing-label">{label}</h3>
      <div className="closing-body">{children}</div>
    </div>
  );
}

export function Learned({ children }: { children?: ReactNode }) {
  return (
    <Panel label="What we learned about the question" className="is-learned">
      {children}
    </Panel>
  );
}

export function Changed({ children }: { children?: ReactNode }) {
  return (
    <Panel label="What the method changed" className="is-changed">
      {children}
    </Panel>
  );
}

export function NotEstablished({ children }: { children?: ReactNode }) {
  return (
    <Panel label="What this analysis does not establish" className="is-limits">
      {children}
    </Panel>
  );
}
