import Link from 'next/link';
import { TopBar } from '@/components/book/SiteChrome';
import { book, entryHref, entryLabel, splitPartTitle } from '@/lib/toc';

/**
 * 404, set like a short chapter page: kicker, title, dek, then the contents
 * grouped by part in the sidebar's grammar (label column, title column).
 */
export default function NotFound() {
  return (
    <>
      <TopBar />
      <main id="main" className="bk-simple">
        <header className="bk-header">
          <p className="bk-kicker">
            <span className="n">Error 404</span>
          </p>
          <h1 className="bk-title">Page not found</h1>
          <p className="bk-dek">
            Nothing lives at this address. The contents are below, or return to the <Link href="/">cover</Link>.
          </p>
        </header>
        <nav className="bk-simple-toc" aria-label="Book contents">
          {book.parts.map((part) => {
            const { label, name } = splitPartTitle(part.title);
            return (
              <section key={part.title} className="bk-simple-part">
                <h2>
                  <span className="lbl">{label ?? name}</span>
                  {label ? <span className="name"> {name}</span> : null}
                </h2>
                <ol>
                  {part.entries.map((e) => (
                    <li key={e.slug}>
                      <Link href={entryHref(e)}>
                        <span className="lbl">{entryLabel(e)}</span>
                        <span className="t">{e.title}</span>
                      </Link>
                    </li>
                  ))}
                </ol>
              </section>
            );
          })}
        </nav>
      </main>
    </>
  );
}
