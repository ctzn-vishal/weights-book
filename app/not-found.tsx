import Link from 'next/link';
import { TopBar } from '@/components/book/SiteChrome';
import { allEntries, entryHref, entryLabel } from '@/lib/toc';

export default function NotFound() {
  return (
    <>
      <TopBar />
      <main id="main" className="bk-simple">
        <h1>Page not found</h1>
        <p>
          Nothing lives at this address. The chapters are listed below, or return to the <Link href="/">cover</Link>.
        </p>
        <ol>
          {allEntries.map((e) => (
            <li key={e.slug}>
              <Link href={entryHref(e)}>
                {entryLabel(e)}: {e.title}
              </Link>
            </li>
          ))}
        </ol>
      </main>
    </>
  );
}
