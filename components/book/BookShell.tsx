import type { ReactNode } from 'react';
import Link from 'next/link';
import { entryHref, entryLabel, kickerFor, type TocEntry, type TocPart } from '@/lib/toc';
import { FactPositioner } from './FactPositioner';
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
                <p className="bk-kicker">{kicker ?? kickerFor(entry, part)}</p>
                <h1 className="bk-title">{entry.title}</h1>
                <p className="bk-dek">{entry.dek}</p>
                {entry.credential ? (
                  <p className="bk-credential">
                    <span className="lbl">Data</span>
                    <span>{entry.credential}</span>
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

function Pager({ prev, next }: { prev: TocEntry | null; next: TocEntry | null }) {
  if (!prev && !next) return null;
  return (
    <nav className="bk-pager" aria-label="Previous and next">
      {prev ? (
        <Link href={entryHref(prev)} className="prev" rel="prev">
          <span className="dir">
            <span aria-hidden="true">← </span>Previous
          </span>
          <span className="lbl">{entryLabel(prev)}</span>
          <span className="t">{prev.title}</span>
        </Link>
      ) : null}
      {next ? (
        <Link href={entryHref(next)} className="next" rel="next">
          <span className="dir">
            Next<span aria-hidden="true"> →</span>
          </span>
          <span className="lbl">{entryLabel(next)}</span>
          <span className="t">{next.title}</span>
        </Link>
      ) : null}
    </nav>
  );
}
