import type { Metadata } from 'next';
import type { ComponentType } from 'react';
import { BookShell } from '@/components/book/BookShell';
import { absoluteUrl } from '@/lib/site';
import { book, findEntry, type TocEntry } from '@/lib/toc';

/** Title, description, and Open Graph for a TOC entry (basePath-safe absolute URLs). */
export function chapterMetadata(entry: TocEntry): Metadata {
  const url = absoluteUrl(`/${entry.slug}`);
  return {
    title: entry.title,
    description: entry.dek,
    alternates: { canonical: url },
    openGraph: {
      type: 'article',
      siteName: book.title,
      title: entry.title,
      description: entry.dek,
      url,
      authors: [book.author],
    },
  };
}

/**
 * One call per chapter page. The integrator writes each app/<slug>/page.tsx as:
 *
 *   import Article from './article.mdx';
 *   import { chapterPage } from '@/lib/chapter-page';
 *   const { metadata, Page } = chapterPage('<slug>', Article);
 *   export { metadata };
 *   export default Page;
 *
 * Throws at build time when the slug is not in lib/toc.ts, so a typo cannot
 * ship a page without its header, navigation, and metadata.
 */
export function chapterPage(slug: string, Article: ComponentType) {
  const loc = findEntry(slug);
  if (!loc) {
    throw new Error(`chapterPage("${slug}"): not a slug in lib/toc.ts. Fix the slug in app/${slug}/page.tsx or add the entry to the TOC.`);
  }
  const { entry, part, prev, next } = loc;
  const metadata = chapterMetadata(entry);

  function Page() {
    return (
      <BookShell entry={entry} part={part} prev={prev} next={next}>
        <Article />
      </BookShell>
    );
  }
  Page.displayName = `ChapterPage(${slug})`;

  return { metadata, Page };
}
