import type { ReactNode } from 'react';
import Link from 'next/link';
import { entryHref, entryLabel, kickerFor, type TocEntry, type TocPart } from '@/lib/toc';
import { FactPositioner } from './FactPositioner';
import { ArrowLeftIcon, ArrowRightIcon } from './icons';
import { MobileNav } from './MobileNav';
import { OnThisPage } from './OnThisPage';
import { TocNav } from './Sidebar';
import { TopBar } from './SiteChrome';

export interface BookShellProps {
  entry: TocEntry;
  /** The entry's part; null for pages outside the book (the kitchen sink). */
  part: TocPart | null;
  prev: TocEntry | null;
  next: TocEntry | null;
  /** Overrides the kicker computed from part and number. */
  kicker?: string;
  /** False for pages that are not TOC entries: nothing is marked current. */
  inToc?: boolean;
  children: ReactNode;
}

/**
 * The reading layout for every chapter, lab, appendix, and placeholder:
 * sticky top bar; contents sidebar (a drawer below lg); the article column
 * with its right margin for sidenotes (xl+); an "On this page" rail (wide
 * screens); chapter header; prev/next. The article body is marked
 * data-article-body, which "On this page" reads its headings from.
 */
export function BookShell({ entry, part, prev, next, kicker, inToc = true, children }: BookShellProps) {
  const current = inToc ? entry.slug : undefined;
  return (
    <>
      <TopBar
        menu={
          <MobileNav showSections>
            <TocNav currentSlug={current} />
          </MobileNav>
        }
      />
      <div className="bk-shell">
        <div className="bk-sidebar">
          <TocNav currentSlug={current} sections />
        </div>
        <main id="main" className="bk-main">
          <div className="bk-page">
            <article className="bk-article">
              <header className="bk-header">
                <Kicker text={kicker ?? kickerFor(entry, part)} />
                <h1 className="bk-title">{entry.title}</h1>
                <p className="bk-dek">{entry.dek}</p>
                {entry.credential ? (
                  <p className="bk-credential">
                    <span className="lbl">Data</span>
                    <span className="val">{entry.credential}</span>
                  </p>
                ) : null}
              </header>
              <div className="bk-prose" data-article-body="">
                {children}
              </div>
              <Pager prev={prev} next={next} />
            </article>
            <div className="bk-rail">
              <OnThisPage key={entry.slug} variant="rail" />
            </div>
          </div>
        </main>
      </div>
      <FactPositioner />
    </>
  );
}

/**
 * "Part II · Chapter 7": the part in muted ink, the entry's own label in the
 * accent, a hairline between. A kicker without a separator (an appendix, an
 * override) is one span.
 */
function Kicker({ text }: { text: string }) {
  const parts = text.split(' · ');
  return (
    <p className="bk-kicker">
      {parts.map((p, i) => (
        // the space keeps "Part II" and "Chapter 7" as two words for assistive tech; the hairline is CSS
        <span key={i} className={i === parts.length - 1 ? 'n' : 'p'}>
          {i > 0 ? ' ' : null}
          {p}
        </span>
      ))}
    </p>
  );
}

/**
 * Prev/next as two cards: a small uppercase line with the direction and the
 * neighbour's label ("Chapter 8"), then its title. The arrow slides on hover.
 * A page with only a "next" keeps it on the right.
 */
function Pager({ prev, next }: { prev: TocEntry | null; next: TocEntry | null }) {
  if (!prev && !next) return null;
  return (
    <nav className="bk-pager" aria-label="Previous and next">
      {prev ? (
        <Link href={entryHref(prev)} className="prev" rel="prev">
          <span className="dir">
            <ArrowLeftIcon className="arr" />
            <span>Previous</span>
            <span className="lbl">{entryLabel(prev)}</span>
          </span>
          <span className="t">{prev.title}</span>
        </Link>
      ) : null}
      {next ? (
        <Link href={entryHref(next)} className="next" rel="next">
          <span className="dir">
            <span className="lbl">{entryLabel(next)}</span>
            <span>Next</span>
            <ArrowRightIcon className="arr" />
          </span>
          <span className="t">{next.title}</span>
        </Link>
      ) : null}
    </nav>
  );
}
