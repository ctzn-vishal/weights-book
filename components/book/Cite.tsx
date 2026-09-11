import { Fragment, type ReactNode } from 'react';
import { getReference } from '@/lib/registry';
import type { Reference } from '@/lib/types';

/** Full reference, for the link's hover title. */
function fullReference(r: Reference): string {
  const who = r.authors?.length ? r.authors.join(', ') : r.short;
  let s = `${who} (${r.year}). ${r.title}.`;
  if (r.venue) {
    s += ` ${r.venue}`;
    if (r.volume) s += ` ${r.volume}`;
    if (r.issue) s += `(${r.issue})`;
    if (r.pages) s += `: ${r.pages}`;
    s += '.';
  } else if (r.publisher) {
    s += ` ${r.publisher}.`;
  }
  return s;
}

function joinWith(parts: ReactNode[], sep: string): ReactNode[] {
  return parts.map((p, i) => (
    <Fragment key={i}>
      {i > 0 ? sep : null}
      {p}
    </Fragment>
  ));
}

/** "A and B"; "A, B, and C". */
function joinAnd(parts: ReactNode[]): ReactNode[] {
  if (parts.length < 3) return joinWith(parts, ' and ');
  return parts.map((p, i) => (
    <Fragment key={i}>
      {i === 0 ? null : i === parts.length - 1 ? ', and ' : ', '}
      {p}
    </Fragment>
  ));
}

/**
 * Author–year citation from data/references.json.
 *   <Cite id="solon2015" />             (Solon, Haider, and Wooldridge 2015)
 *   <Cite id="solon2015" narrative />   Solon, Haider, and Wooldridge (2015)
 *   <Cite id="kish1965, horvitz1952" /> (Kish 1965; Horvitz and Thompson 1952)
 * Each work links to its DOI (or URL). An unknown key fails the build.
 */
export function Cite({ id, narrative = false }: { id: string; narrative?: boolean }) {
  const keys = id.split(',').map((s) => s.trim()).filter(Boolean);
  if (!keys.length) throw new Error('<Cite>: empty id');
  const works = keys.map((k) => {
    const r = getReference(k);
    const href = r.doi ? `https://doi.org/${r.doi}` : r.url || null;
    const text = narrative ? `${r.short} (${r.year})` : `${r.short} ${r.year}`;
    const title = fullReference(r);
    return href ? (
      <a key={k} href={href} title={title} rel="noopener noreferrer">
        {text}
      </a>
    ) : (
      <span key={k} title={title}>
        {text}
      </span>
    );
  });
  if (narrative) return <span className="cite">{joinAnd(works)}</span>;
  return <span className="cite">({joinWith(works, '; ')})</span>;
}
