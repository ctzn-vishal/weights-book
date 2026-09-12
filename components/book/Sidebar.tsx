import Link from 'next/link';
import { hasChapterPage } from '@/lib/pages';
import { book, entryHref, entryKind, splitPartTitle } from '@/lib/toc';
import { OnThisPage, RevealCurrent } from './OnThisPage';

/**
 * The book's contents: parts, then chapters, labs, and appendices, with the
 * current page marked. Rendered twice per page (the lg+ sidebar and the
 * mobile drawer); `sections` nests the current chapter's h2 list under its
 * entry, which the sidebar uses between lg and the width where the separate
 * "On this page" rail appears. Every row shares one two-column grid (number,
 * title), so chapter numbers, appendix letters, and the lab tag line up and
 * every title starts at the same x; the current entry is scrolled into view
 * on arrival.
 */
export function TocNav({ currentSlug, sections = false }: { currentSlug?: string; sections?: boolean }) {
  return (
    <nav className="bk-toc" aria-label="Book contents">
      <Link href="/" className="bk-toc-home">
        {book.title}
      </Link>
      {book.parts.map((part) => {
        const { label, name } = splitPartTitle(part.title);
        return (
          <div key={part.title} className="bk-toc-part" role="group" aria-label={part.title}>
            <p className="bk-toc-part-title">
              <span className="lbl">{label ?? name}</span>
              {label ? <span className="name">{name}</span> : null}
            </p>
            <ol>
              {part.entries.map((e) => {
                const current = e.slug === currentSlug;
                const lab = entryKind(e) === 'lab';
                return (
                  <li key={e.slug}>
                    <Link
                      href={entryHref(e)}
                      className={lab ? 'bk-toc-link is-lab' : 'bk-toc-link'}
                      aria-current={current ? 'page' : undefined}
                    >
                      {/* the lab tag is visual only: a lab's title already begins "Lab:" */}
                      <span className="bk-toc-num" aria-hidden={lab ? 'true' : undefined}>
                        {lab ? 'Lab' : e.number}
                      </span>
                      <span className="bk-toc-title">
                        {e.title}
                        {hasChapterPage(e.slug) ? null : (
                          <span className="bk-toc-pending" title="Being drafted">
                            soon
                          </span>
                        )}
                      </span>
                    </Link>
                    {current && sections ? (
                      <div className="bk-toc-sections">
                        <OnThisPage variant="nested" />
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ol>
          </div>
        );
      })}
      {currentSlug ? <RevealCurrent /> : null}
    </nav>
  );
}
